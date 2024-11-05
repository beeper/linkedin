package connector

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"path"
	"time"

	"go.mau.fi/util/ptr"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/database"
	"maunium.net/go/mautrix/bridgev2/networkid"
	bridgeEvt "maunium.net/go/mautrix/event"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/payload"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/query"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

func MakeAvatar(avatarURL string) *bridgev2.Avatar {
	return &bridgev2.Avatar{
		ID: networkid.AvatarID(avatarURL),
		Get: func(ctx context.Context) ([]byte, error) {
			req, err := http.NewRequestWithContext(ctx, http.MethodGet, avatarURL, nil)
			if err != nil {
				return nil, fmt.Errorf("failed to prepare request: %w", err)
			}

			getResp, err := http.DefaultClient.Do(req)
			if err != nil {
				return nil, fmt.Errorf("failed to download avatar: %w", err)
			}

			data, err := io.ReadAll(getResp.Body)
			_ = getResp.Body.Close()
			if err != nil {
				return nil, fmt.Errorf("failed to read avatar data: %w", err)
			}
			return data, err
		},
		Remove: avatarURL == "",
	}
}

func (lc *LinkedInClient) ConversationToChatInfo(thread *response.ThreadElement) *bridgev2.ChatInfo {
	memberList := lc.ParticipantsToMemberList(thread.ConversationParticipants)
	return &bridgev2.ChatInfo{
		Name:        &thread.Title,
		Members:     memberList,
		Type:        lc.ConversationTypeToRoomType(thread.GroupChat),
		CanBackfill: true,
	}
}

func (lc *LinkedInClient) ConversationTypeToRoomType(isGroupChat bool) *database.RoomType {
	var roomType database.RoomType
	if isGroupChat {
		roomType = database.RoomTypeGroupDM
	} else {
		roomType = database.RoomTypeDM
	}
	return &roomType
}

func (lc *LinkedInClient) ParticipantsToMemberList(participants []types.ConversationParticipant) *bridgev2.ChatMemberList {
	selfUserId := lc.client.GetCurrentUserID()
	memberMap := map[networkid.UserID]bridgev2.ChatMember{}
	for _, participant := range participants {
		memberMap[networkid.UserID(participant.HostIdentityUrn)] = lc.ParticipantToChatMember(participant, participant.HostIdentityUrn == selfUserId)
	}

	return &bridgev2.ChatMemberList{
		IsFull:           true,
		TotalMemberCount: len(participants),
		MemberMap:        memberMap,
	}
}

func (lc *LinkedInClient) ParticipantToChatMember(participant types.ConversationParticipant, isFromMe bool) bridgev2.ChatMember {
	member := participant.ParticipantType.Member
	if participant.ParticipantType.Organization != nil || participant.ParticipantType.Custom != nil {
		return bridgev2.ChatMember{}
	}
	return bridgev2.ChatMember{
		EventSender: bridgev2.EventSender{
			IsFromMe: isFromMe,
			Sender:   networkid.UserID(participant.HostIdentityUrn),
		},
		UserInfo: lc.getUserInfoMember(member),
	}
}

func (lc *LinkedInClient) GetUserInfoBridge(userUrn string) *bridgev2.UserInfo {
	var userinfo *bridgev2.UserInfo
	if member, ok := lc.userCache[userUrn]; ok { // implement user cache
		userinfo = lc.getUserInfoMember(member)
	}
	return userinfo
}

func (lc *LinkedInClient) getUserInfoMember(member types.Member) *bridgev2.UserInfo {
	return &bridgev2.UserInfo{
		Name:        ptr.Ptr(lc.connector.Config.FormatDisplayname(member.FirstName.Text, member.LastName.Text)),
		Avatar:      MakeAvatar(member.ProfilePicture.RootURL),
		Identifiers: []string{fmt.Sprintf("linkedin:%s", path.Base(member.ProfileURL))},
	}
}

func (lc *LinkedInClient) MessagesToBackfillMessages(ctx context.Context, messages []response.MessageElement, portal *bridgev2.Portal) ([]*bridgev2.BackfillMessage, error) {
	backfilledMessages := make([]*bridgev2.BackfillMessage, 0)
	for _, msg := range messages {
		backfilledMessage, err := lc.MessageToBackfillMessage(ctx, msg, portal)
		if err != nil {
			return nil, err
		}
		backfilledMessages = append(backfilledMessages, backfilledMessage)
	}

	return backfilledMessages, nil
}

func (lc *LinkedInClient) MessageToBackfillMessage(ctx context.Context, message response.MessageElement, portal *bridgev2.Portal) (*bridgev2.BackfillMessage, error) {
	messageReactions, err := lc.MessageReactionsToBackfillReactions(message.ReactionSummaries, message.EntityUrn)
	if err != nil {
		return nil, err
	}

	sentAt := time.UnixMilli(message.DeliveredAt)

	intent := lc.userLogin.Bridge.Matrix.BotIntent()
	if err != nil {
		return nil, err
	}

	cm, err := lc.convertToMatrix(ctx, portal, intent, &message)
	if err != nil {
		return nil, err
	}

	return &bridgev2.BackfillMessage{
		ConvertedMessage: cm,
		Sender: bridgev2.EventSender{
			IsFromMe: message.Sender.EntityUrn == lc.client.GetCurrentUserID(),
			Sender:   networkid.UserID(message.Sender.EntityUrn),
		},
		ID:        networkid.MessageID(message.EntityUrn),
		Timestamp: sentAt,
		Reactions: messageReactions,
	}, nil
}

func (lc *LinkedInClient) MessageReactionsToBackfillReactions(reactions []response.ReactionSummary, messageUrn string) ([]*bridgev2.BackfillReaction, error) {
	backfillReactions := make([]*bridgev2.BackfillReaction, 0)
	for _, reaction := range reactions {
		participants, err := lc.client.GetReactionsForEmoji(query.GetReactionsForEmojiVariables{
			Emoji:      reaction.Emoji,
			MessageUrn: messageUrn,
		})
		if err != nil {
			return nil, err
		}

		for _, participant := range participants {
			backfillReaction := &bridgev2.BackfillReaction{
				Timestamp: time.UnixMilli(reaction.FirstReactedAt),
				Sender: bridgev2.EventSender{
					IsFromMe: participant.HostIdentityUrn == lc.client.GetCurrentUserID(),
					Sender:   networkid.UserID(participant.HostIdentityUrn),
				},
				EmojiID: "",
				Emoji:   reaction.Emoji,
			}
			backfillReactions = append(backfillReactions, backfillReaction)
		}
	}
	return backfillReactions, nil
}

var (
	ErrUnsupportedAttachmentType = errors.New("unsupported attachment type")
)

func (lc *LinkedInClient) LinkedInAttachmentToMatrix(ctx context.Context, portal *bridgev2.Portal, intent bridgev2.MatrixAPI, content payload.RenderContent) (*bridgev2.ConvertedMessagePart, error) {
	var attachmentURL string
	var mimeType string
	var msgType bridgeEvt.MessageType
	var attachmentSize int
	var duration int
	var height int
	var width int
	if image := content.VectorImage; image != nil {
		// image attachment
		msgType = bridgeEvt.MsgImage
		attachmentURL = image.RootURL
	} else if video := content.Video; video != nil {
		// video attachment
		attachmentURL = video.ProgressiveStreams[0].StreamingLocations[0].Url
		mimeType = video.ProgressiveStreams[0].MediaType
		msgType = bridgeEvt.MsgVideo
		attachmentSize = video.ProgressiveStreams[0].Size
		height = video.ProgressiveStreams[0].Height
		width = video.ProgressiveStreams[0].Width
	} else if audio := content.Audio; audio != nil {
		// video attachment
		attachmentURL = audio.URL
		msgType = bridgeEvt.MsgAudio
		duration = audio.Duration
	} else if file := content.File; file != nil {
		// video attachment
		attachmentURL = file.URL
		mimeType = string(file.MediaType)
		msgType = bridgeEvt.MsgFile
		attachmentSize = file.ByteSize
	} else {
		return nil, ErrUnsupportedAttachmentType
	}

	cookieString := lc.client.GetCookieString()

	var err error

	if attachmentSize == 0 {
		attachmentSize, err = GetFileSize(ctx, cookieString, attachmentURL)
		if err != nil {
			return nil, err
		}
	}

	uploadContent := bridgeEvt.MessageEventContent{
		Info: &bridgeEvt.FileInfo{
			MimeType: mimeType,
			Height:   height,
			Width:    width,
			Duration: duration,
			Size:     attachmentSize,
		},
		MsgType: msgType,
		Body:    "",
	}

	uploadContent.URL, uploadContent.File, err = intent.UploadMediaStream(ctx, portal.MXID, int64(attachmentSize), true, func(file io.Writer) (*bridgev2.FileStreamResult, error) {
		err = GetPlainFileStream(ctx, cookieString, attachmentURL, "linkedin attachment", file)
		if err != nil {
			return nil, err
		}

		return &bridgev2.FileStreamResult{MimeType: uploadContent.Info.MimeType}, nil
	})

	if err != nil {
		return nil, err
	}

	return &bridgev2.ConvertedMessagePart{
		ID:      networkid.PartID(""),
		Type:    bridgeEvt.EventMessage,
		Content: &uploadContent,
	}, nil
}

func GetPlainFileStream(ctx context.Context, cookies, url, thing string, writer io.Writer) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("failed to prepare request: %w", err)
	}

	if cookies != "" {
		req.Header.Add("cookie", cookies)
	}

	getResp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to download %s: %w", thing, err)
	}

	_, err = io.Copy(writer, getResp.Body)
	if err != nil {
		return fmt.Errorf("failed to read %s data: %w", thing, err)
	}

	return nil
}

func GetFileSize(ctx context.Context, cookies, url string) (int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodHead, url, nil)
	if err != nil {
		return 0, fmt.Errorf("failed to prepare request: %w", err)
	}

	if cookies != "" {
		req.Header.Add("cookie", cookies)
	}

	headResp, err := http.DefaultClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("failed to get file size: %w", err)
	}

	return int(headResp.ContentLength), nil
}
