package connector

import (
	"context"
	"fmt"
	"time"

	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/database"
	"maunium.net/go/mautrix/bridgev2/networkid"
	"maunium.net/go/mautrix/event"

	"github.com/beeper/linkedin/pkg/linkedingo/routing/payload"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

var (
	_ bridgev2.ReactionHandlingNetworkAPI    = (*LinkedInClient)(nil)
	_ bridgev2.ReadReceiptHandlingNetworkAPI = (*LinkedInClient)(nil)
	_ bridgev2.EditHandlingNetworkAPI        = (*LinkedInClient)(nil)
	_ bridgev2.TypingHandlingNetworkAPI      = (*LinkedInClient)(nil)
)

func (lc *LinkedInClient) HandleMatrixTyping(_ context.Context, msg *bridgev2.MatrixTyping) error {
	if msg.IsTyping && msg.Type == bridgev2.TypingTypeText {
		return lc.client.StartTyping(string(msg.Portal.ID))
	}
	return nil
}

func (lc *LinkedInClient) HandleMatrixMessage(ctx context.Context, msg *bridgev2.MatrixMessage) (message *bridgev2.MatrixMessageResponse, err error) {
	conversationUrn := string(msg.Portal.ID)
	sendMessagePayload := payload.SendMessagePayload{
		Message: payload.SendMessageData{
			Body: payload.MessageBody{
				Text: msg.Content.Body,
			},
			ConversationUrn:     conversationUrn,
			RenderContentUnions: []payload.RenderContent{},
		},
	}

	if msg.ReplyTo != nil {
		sendMessagePayload.Message.RenderContentUnions = append(
			sendMessagePayload.Message.RenderContentUnions,
			payload.RenderContent{
				RepliedMessageContent: &payload.RepliedMessageContent{
					OriginalSenderUrn:  string(msg.ReplyTo.SenderID),
					OriginalMessageUrn: string(msg.ReplyTo.ID),
					OriginalSendAt:     msg.ReplyTo.Timestamp.UnixMilli(),
					//MessageBody:        "", // todo add at some point
				},
			},
		)
	}

	content := msg.Content

	switch content.MsgType {
	case event.MsgText:
		break
	case event.MsgVideo, event.MsgImage:
		if content.Body == content.FileName {
			sendMessagePayload.Message.Body.Text = ""
		}

		file := content.GetFile()
		data, err := lc.connector.br.Bot.DownloadMedia(ctx, file.URL, file)
		if err != nil {
			return nil, err
		}

		attachmentType := payload.MediaUploadFileAttachment
		if content.MsgType == event.MsgImage {
			attachmentType = payload.MediaUploadTypePhotoAttachment
		}

		mediaMetadata, err := lc.client.UploadMedia(attachmentType, content.FileName, data, types.ContentTypeJSONPlaintextUTF8)
		if err != nil {
			return nil, err
		}

		lc.client.Logger.Debug().Any("media_metadata", mediaMetadata).Msg("Successfully uploaded media to LinkedIn's servers")
		sendMessagePayload.Message.RenderContentUnions = append(sendMessagePayload.Message.RenderContentUnions, payload.RenderContent{
			File: &payload.File{
				AssetUrn:  mediaMetadata.Urn,
				Name:      content.FileName,
				MediaType: types.ContentType(content.Info.MimeType),
				ByteSize:  len(data),
			},
		})
	default:
		return nil, fmt.Errorf("%w %s", bridgev2.ErrUnsupportedMessageType, content.MsgType)
	}

	resp, err := lc.client.SendMessage(sendMessagePayload)
	if err != nil {
		return nil, err
	}

	return &bridgev2.MatrixMessageResponse{
		DB: &database.Message{
			ID:        networkid.MessageID(resp.Data.EntityUrn),
			MXID:      msg.Event.ID,
			Room:      msg.Portal.PortalKey,
			SenderID:  networkid.UserID(lc.client.GetCurrentUserID()),
			Timestamp: time.UnixMilli(resp.Data.DeliveredAt),
		},
	}, nil
}

func (lc *LinkedInClient) PreHandleMatrixReaction(_ context.Context, msg *bridgev2.MatrixReaction) (bridgev2.MatrixReactionPreResponse, error) {
	return bridgev2.MatrixReactionPreResponse{
		SenderID:     networkid.UserID(lc.userLogin.ID),
		Emoji:        msg.Content.RelatesTo.Key,
		MaxReactions: 1,
	}, nil
}

func (lc *LinkedInClient) HandleMatrixReactionRemove(_ context.Context, msg *bridgev2.MatrixReactionRemove) error {
	return lc.doHandleMatrixReaction(false, string(msg.TargetReaction.MessageID), msg.TargetReaction.Emoji)
}

func (lc *LinkedInClient) HandleMatrixReaction(_ context.Context, msg *bridgev2.MatrixReaction) (reaction *database.Reaction, err error) {
	return nil, lc.doHandleMatrixReaction(true, string(msg.TargetMessage.ID), msg.PreHandleResp.Emoji)
}

func (lc *LinkedInClient) doHandleMatrixReaction(react bool, messageUrn, emoji string) error {
	reactionPayload := payload.SendReactionPayload{
		MessageUrn: messageUrn,
	}
	err := lc.client.SendReaction(reactionPayload, react)
	if err != nil {
		return err
	}

	lc.client.Logger.Debug().Any("payload", reactionPayload).Msg("Reaction response")
	return nil
}

func (lc *LinkedInClient) HandleMatrixReadReceipt(ctx context.Context, msg *bridgev2.MatrixReadReceipt) error {
	_, err := lc.client.MarkThreadRead([]string{string(msg.Portal.ID)}, true)
	return err
}

func (lc *LinkedInClient) HandleMatrixEdit(_ context.Context, edit *bridgev2.MatrixEdit) error {
	return lc.client.EditMessage(string(edit.EditTarget.ID), payload.MessageBody{
		Text: edit.Content.Body,
	})
}
