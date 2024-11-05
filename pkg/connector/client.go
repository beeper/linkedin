package connector

import (
	"context"
	"fmt"
	"time"

	"github.com/rs/zerolog"
	"maunium.net/go/mautrix/bridge/status"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/database"
	"maunium.net/go/mautrix/bridgev2/networkid"
	bridgeEvt "maunium.net/go/mautrix/event"

	"github.com/beeper/linkedin/pkg/linkedingo"
	"github.com/beeper/linkedin/pkg/linkedingo/cookies"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type LinkedInClient struct {
	connector *LinkedInConnector
	client    *linkedingo.Client

	userLogin *bridgev2.UserLogin

	userCache   map[string]types.Member
	threadCache map[string]response.ThreadElement
}

var (
	_ bridgev2.NetworkAPI = (*LinkedInClient)(nil)
)

func NewLinkedInClient(ctx context.Context, tc *LinkedInConnector, login *bridgev2.UserLogin) *LinkedInClient {
	log := zerolog.Ctx(ctx).With().
		Str("component", "twitter_client").
		Str("user_login_id", string(login.ID)).
		Logger()

	meta := login.Metadata.(*UserLoginMetadata)
	clientOpts := &linkedingo.ClientOpts{
		Cookies: cookies.NewCookiesFromString(meta.Cookies),
	}
	linClient := &LinkedInClient{
		client:      linkedingo.NewClient(clientOpts, log),
		userLogin:   login,
		userCache:   make(map[string]types.Member),
		threadCache: make(map[string]response.ThreadElement),
	}

	//twitClient.client.SetEventHandler(twitClient.HandleTwitterEvent) // todo set event listener
	linClient.connector = tc
	return linClient
}

func (lc *LinkedInClient) Connect(ctx context.Context) error {
	if lc.client == nil {
		lc.userLogin.BridgeState.Send(status.BridgeState{
			StateEvent: status.StateBadCredentials,
			Error:      "linkedin-not-logged-in",
		})
		return nil
	}

	err := lc.client.LoadMessagesPage()
	if err != nil {
		return fmt.Errorf("failed to load messages page")
	}

	profile, err := lc.client.GetCurrentUserProfile()

	lc.userLogin.RemoteName = fmt.Sprintf("%s %s", profile.MiniProfile.FirstName, profile.MiniProfile.LastName)
	lc.userLogin.Save(ctx)

	err = lc.client.Connect()
	if err != nil {
		return fmt.Errorf("failed to connect to linkedin client: %w", err)
	}
	lc.userLogin.BridgeState.Send(status.BridgeState{StateEvent: status.StateConnected})

	go lc.syncChannels(ctx)
	return nil
}

func (lc *LinkedInClient) Disconnect() {
	err := lc.client.Disconnect()
	if err != nil {
		lc.userLogin.Log.Error().Err(err).Msg("failed to disconnect, err:")
	}
}

func (lc *LinkedInClient) IsLoggedIn() bool {
	return ValidCookieRegex.MatchString(lc.userLogin.Metadata.(UserLoginMetadata).Cookies)
}

func (lc *LinkedInClient) LogoutRemote(ctx context.Context) {
	log := zerolog.Ctx(ctx)
	err := lc.client.Logout()
	if err != nil {
		log.Error().Err(err).Msg("error logging out")
	}
}

func (lc *LinkedInClient) IsThisUser(_ context.Context, userID networkid.UserID) bool {
	return networkid.UserID(lc.client.GetCurrentUserID()) == userID
}

func (lc *LinkedInClient) GetCurrentUser() (user *types.UserLoginProfile, err error) {
	user, err = lc.client.GetCurrentUserProfile()
	return
}

func (lc *LinkedInClient) GetChatInfo(_ context.Context, portal *bridgev2.Portal) (*bridgev2.ChatInfo, error) {
	// not supported
	return nil, nil
}

func (lc *LinkedInClient) GetUserInfo(_ context.Context, ghost *bridgev2.Ghost) (*bridgev2.UserInfo, error) {
	userInfo := lc.GetUserInfoBridge(string(ghost.ID))
	if userInfo == nil {
		return nil, fmt.Errorf("failed to find user info in cache by id: %s", ghost.ID)
	}
	return userInfo, nil
}

func (lc *LinkedInClient) GetCapabilities(_ context.Context, _ *bridgev2.Portal) *bridgev2.NetworkRoomCapabilities {
	return &bridgev2.NetworkRoomCapabilities{ // todo update
		FormattedText: false,
		UserMentions:  true,
		RoomMentions:  false,

		Edits:         true,
		EditMaxCount:  10,
		EditMaxAge:    15 * time.Minute,
		Captions:      true,
		Replies:       true,
		Reactions:     true,
		ReactionCount: 1,
	}
}

func (lc *LinkedInClient) convertEditToMatrix(ctx context.Context, portal *bridgev2.Portal, intent bridgev2.MatrixAPI, existing []*database.Message, data *response.MessageElement) (*bridgev2.ConvertedEdit, error) {
	converted, err := lc.convertToMatrix(ctx, portal, intent, data)
	if err != nil {
		return nil, err
	}
	return &bridgev2.ConvertedEdit{
		ModifiedParts: []*bridgev2.ConvertedEditPart{converted.Parts[0].ToEditPart(existing[0])},
	}, nil
}

func (lc *LinkedInClient) convertToMatrix(ctx context.Context, portal *bridgev2.Portal, intent bridgev2.MatrixAPI, msg *response.MessageElement) (*bridgev2.ConvertedMessage, error) {
	var replyTo *networkid.MessageOptionalPartID
	parts := make([]*bridgev2.ConvertedMessagePart, 0)

	for _, renderContent := range msg.RenderContent {
		if renderContent.RepliedMessageContent.OriginalMessageUrn != "" {
			replyTo = &networkid.MessageOptionalPartID{
				MessageID: networkid.MessageID(renderContent.RepliedMessageContent.OriginalMessageUrn),
			}
		} else {
			convertedPart, err := lc.LinkedInAttachmentToMatrix(ctx, portal, intent, renderContent)
			if err != nil {
				return nil, err
			}
			if convertedPart != nil {
				parts = append(parts, convertedPart)
			}
		}
	}

	textPart := &bridgev2.ConvertedMessagePart{
		ID:   "",
		Type: bridgeEvt.EventMessage,
		Content: &bridgeEvt.MessageEventContent{
			MsgType: bridgeEvt.MsgText,
			Body:    msg.Body.Text,
		},
	}

	if len(textPart.Content.Body) > 0 {
		parts = append(parts, textPart)
	}

	cm := &bridgev2.ConvertedMessage{
		ReplyTo: replyTo,
		Parts:   parts,
	}

	cm.MergeCaption() // merges captions and media onto one part

	return cm, nil
}

func (lc *LinkedInClient) MakePortalKey(thread response.ThreadElement) networkid.PortalKey {
	var receiver networkid.UserLoginID
	if !thread.GroupChat {
		receiver = lc.userLogin.ID
	}
	return networkid.PortalKey{
		ID:       networkid.PortalID(thread.EntityUrn),
		Receiver: receiver,
	}
}
