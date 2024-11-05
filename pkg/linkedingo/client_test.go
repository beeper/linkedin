package linkedingo_test

import (
	"log"
	"os"
	"testing"

	"github.com/beeper/linkedin/pkg/linkedingo"
	"github.com/beeper/linkedin/pkg/linkedingo/cookies"
	"github.com/beeper/linkedin/pkg/linkedingo/debug"
	"github.com/beeper/linkedin/pkg/linkedingo/event"
)

var cli *linkedingo.Client

func TestClientMain(t *testing.T) {
	cookieStr, err := os.ReadFile("cookies.txt")
	if err != nil {
		log.Fatal(err)
	}
	cookieStruct := cookies.NewCookiesFromString(string(cookieStr))

	clientOpts := linkedingo.ClientOpts{
		Cookies: cookieStruct,
	}
	cli = linkedingo.NewClient(&clientOpts, debug.NewLogger())
	cli.SetEventHandler(evHandler)

	err = cli.LoadMessagesPage()
	if err != nil {
		log.Fatalf("error while loading main messaging page: %s", err.Error())
	}

	err = cli.Connect()
	if err != nil {
		log.Fatal(err)
	}

	wait := make(chan struct{})
	<-wait
}

func evHandler(data any) {
	switch evtData := data.(type) {
	case event.MessageEvent:
		cli.Logger.Info().Str("text", evtData.Message.Body.Text).Msg("Received message event")
	case event.SystemMessageEvent:
		cli.Logger.Info().Str("text", evtData.Message.Body.Text).Msg("Received a system message event")
	case event.MessageEditedEvent:
		cli.Logger.Info().Str("text", evtData.Message.Body.Text).Msg("Received message edited event")
	case event.MessageDeleteEvent:
		cli.Logger.Info().Str("text", evtData.Message.Body.Text).Msg("Received message delete event")
	case event.MessageSeenEvent:
		cli.Logger.Info().Any("receipt", evtData.Receipt).Msg("Received message seen event")
	case event.MessageReactionEvent:
		cli.Logger.Info().Any("reaction", evtData.Reaction).Msg("Received message reaction event")
	case event.TypingIndicatorEvent:
		cli.Logger.Info().Any("indicator", evtData.Indicator).Msg("Received typing indicator event")
	case event.ThreadDeleteEvent:
		cli.Logger.Info().Str("thread_id", evtData.Thread.EntityUrn).Msg("Thread was deleted")
	case event.ThreadUpdateEvent:
		cli.Logger.Info().Any("thread_id", evtData.Thread.EntityUrn).Msg("Thread was updated")
	case event.ConnectionReady:
		cli.Logger.Info().Msg("Real-time client is connected and ready")
	case event.ConnectionClosed:
		cli.Logger.Error().Str("reason", string(evtData.Reason)).Msg("Real-time client closed the connection")
		cli.Logger.Info().Msg("Attempting to reconnect real-time client")
		err := cli.Connect()
		if err != nil {
			cli.Logger.Fatal().Err(err).Msg("Real-time client failed to reconnect")
		}
	default:
		cli.Logger.Info().Any("evt_data", evtData).Msg("Received unhandled event struct")
	}
}

/*
func testDeleteConversation() {
	firstThread := getTopThread()

	err := cli.DeleteConversation(firstThread.EntityUrn)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().Str("conversationUrn", firstThread.EntityUrn).Msg("Successfully deleted conversation")
	os.Exit(1)
}

func testCreateConversation() {
	// there is not any other endpoint for creating convos, you just send a message with recipient urns instead of conversation urn
	participantIds := []string{
		"user:id:urn:1",
		"user:id:urn:2",
	}
	createConvoPayload := payload.SendMessagePayload{
		Message: payload.SendMessageData{
			Body: payload.MessageBody{
				Text: "new convo created",
			},
		},
		DedupeByClientGeneratedToken: false,
		HostRecipientUrns:            participantIds,
		ConversationTitle:            "test title",
	}

	messageResp, err := cli.SendMessage(createConvoPayload)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().Any("create_conv_msg_resp", messageResp).Any("participant_ids", participantIds).Msg("Successfully created conversation")
	os.Exit(1)
}

func testReadConversations() {
	threads, err := cli.GetThreads(query.GetThreadsVariables{})
	if err != nil {
		log.Fatal(err)
	}

	pickedThreadUrns := make([]string, 0)
	for _, thread := range threads.Threads {
		if !thread.Read {
			pickedThreadUrns = append(pickedThreadUrns, thread.EntityUrn)
		}
	}

	if len(pickedThreadUrns) == 0 {
		log.Fatal("failed to find an unread thread to read")
	}

	resp, err := cli.MarkThreadRead(pickedThreadUrns, true)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().Any("response_data", resp).Any("thread_ids", pickedThreadUrns).Msg("Successfully read threads!")
	os.Exit(1)
}

func testReplyToMessage() {
	firstThread := getTopThread()
	firstMessage := firstThread.MessageElements.Messages[0]

	replyMessageBody := payload.SendMessagePayload{
		Message: payload.SendMessageData{
			Body: payload.MessageBody{
				Text: "testing to reply to message",
			},
			RenderContentUnions: []payload.RenderContent{
				{
					RepliedMessageContent: &payload.RepliedMessageContent{
						OriginalSenderUrn:  firstMessage.Sender.EntityUrn,
						OriginalMessageUrn: firstMessage.EntityUrn,
						MessageBody:        firstMessage.Body,
						OriginalSendAt:     firstMessage.DeliveredAt,
					},
				},
			},
			ConversationUrn: firstThread.EntityUrn,
		},
		DedupeByClientGeneratedToken: false,
	}

	messageResp, err := cli.SendMessage(replyMessageBody)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().Any("message_data", messageResp).Msg("Successfully replied to message")
	os.Exit(1)
}

func testDeleteMessage() {
	firstThread := getTopThread()
	firstThreadUrn := firstThread.EntityUrn

	messages, err := cli.FetchMessages(query.FetchMessagesVariables{
		ConversationUrn: firstThreadUrn,
	})
	if err != nil {
		log.Fatal(err)
	}

	myUserId := cli.GetCurrentUserID()
	var pickedMessage *response.MessageElement
	for _, msg := range messages.Messages {
		if msg.MessageBodyRenderFormat != response.RenderFormatReCalled && myUserId == msg.Sender.HostIdentityUrn {
			pickedMessage = &msg
			break
		}
	}

	if pickedMessage == nil {
		log.Fatalf("failed to find a valid message to delete in conversation with urn %s", firstThreadUrn)
	}

	messageUrn := pickedMessage.EntityUrn
	err = cli.DeleteMessage(messageUrn)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().Str("text", pickedMessage.Body.Text).Str("conversationUrn", firstThreadUrn).Msg("Successfully deleted message in conversation")
	os.Exit(1)
}

func testLogAllMessages() {
	firstThread := getTopThread()
	firstThreadUrn := firstThread.EntityUrn

	variables := query.FetchMessagesVariables{
		ConversationUrn: firstThreadUrn,
	}
	messageResp, err := cli.FetchMessages(variables)
	if err != nil {
		log.Fatal(err)
	}

	lastMessage := messageResp.Messages[len(messageResp.Messages)-1]
	variables.DeliveredAt = lastMessage.DeliveredAt
	variables.CountBefore = 20
	variables.CountAfter = 0

	messageResp, err = cli.FetchMessages(variables)
	if err != nil {
		log.Fatal(err)
	}

	prevCursor := messageResp.Metadata.PrevCursor
	variables = query.FetchMessagesVariables{
		ConversationUrn: firstThreadUrn,
		PrevCursor:      prevCursor,
		Count:           20,
	}
	for variables.PrevCursor != "" {
		messageResp, err = cli.FetchMessages(variables)
		if err != nil {
			log.Fatal(err)
		}

		for _, msg := range messageResp.Messages {
			cli.Logger.Info().Str("text", msg.Body.Text).Msg("Message")
		}

		variables.PrevCursor = messageResp.Metadata.PrevCursor
	}

	os.Exit(1)
}

func testLogAllThreads() {
	variables := query.GetThreadsVariables{} // empty for first page
	threads, err := cli.GetThreads(variables)
	if err != nil {
		log.Fatal(err)
	}

	lastThread := threads.Threads[len(threads.Threads)-1]
	lastActvityAt := lastThread.LastActivityAt // cursor

	variables.Count = 20
	variables.InboxCategory = query.INBOX_CATEGORY_PRIMARY
	variables.LastUpdatedBefore = lastActvityAt

	threads, err = cli.GetThreads(variables)
	if err != nil {
		log.Fatal(err)
	}

	// now threads.Metadata.NextCursor contains the next cursor to use in variables.
	log.Println("Next cursor:", threads.Metadata.NextCursor)
	os.Exit(1)
}

// starts typing in the top conversation
func testStartTyping() {
	firstThread := getTopThread()
	firstThreadUrn := firstThread.EntityUrn

	err := cli.StartTyping(firstThreadUrn)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().Str("conversationUrn", firstThreadUrn).Msg("Successfully started typing in top conversation")
	os.Exit(1)
}

func testUploadVideo() {
	videoBytes, err := os.ReadFile("test_data/testvideo1.mp4")
	if err != nil {
		log.Fatal(err)
	}

	mediaContentType := types.VIDEO_MP4
	fileName := "testvideo1.mp4"
	mediaResult, err := cli.UploadMedia(payload.MESSAGING_FILE_ATTACHMENT, fileName, videoBytes, mediaContentType)
	if err != nil {
		log.Fatal(err)
	}

	renderContentFile := payload.RenderContent{
		File: &payload.File{
			AssetUrn:  mediaResult.Urn,
			Name:      fileName,
			MediaType: mediaContentType,
			ByteSize:  len(videoBytes),
		},
	}

	firstThread := getTopThread()
	firstThreadUrn := firstThread.EntityUrn

	sendMessagePayload := payload.SendMessagePayload{
		Message: payload.SendMessageData{
			Body: payload.MessageBody{
				Text: "",
			},
			RenderContentUnions: []payload.RenderContent{renderContentFile},
			ConversationUrn:     firstThreadUrn,
		},
		DedupeByClientGeneratedToken: false,
	}

	resp, err := cli.SendMessage(sendMessagePayload)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().
		Any("renderContentUnions", resp.Data.RenderContentUnions).
		Int64("deliveredAt", resp.Data.DeliveredAt).
		Str("text", resp.Data.Body.Text).
		Str("conversationUrn", firstThreadUrn).
		Msg("Successfully sent test video to top conversation")
	os.Exit(1)
}

func testUploadImage() {
	imgBytes, err := os.ReadFile("test_data/testimage1.jpg")
	if err != nil {
		log.Fatal(err)
	}

	mediaContentType := types.IMAGE_JPEG
	fileName := "testimage1.jpg"
	mediaResult, err := cli.UploadMedia(payload.MESSAGING_PHOTO_ATTACHMENT, fileName, imgBytes, mediaContentType)
	if err != nil {
		log.Fatal(err)
	}

	renderContentFile := payload.RenderContent{
		File: &payload.File{
			AssetUrn:  mediaResult.Urn,
			Name:      fileName,
			MediaType: mediaContentType,
			ByteSize:  len(imgBytes),
		},
	}

	firstThread := getTopThread()
	firstThreadUrn := firstThread.EntityUrn

	sendMessagePayload := payload.SendMessagePayload{
		Message: payload.SendMessageData{
			Body: payload.MessageBody{
				Text: "",
			},
			RenderContentUnions: []payload.RenderContent{renderContentFile},
			ConversationUrn:     firstThreadUrn,
		},
		DedupeByClientGeneratedToken: false,
	}

	resp, err := cli.SendMessage(sendMessagePayload)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().
		Any("renderContentUnions", resp.Data.RenderContentUnions).
		Int64("deliveredAt", resp.Data.DeliveredAt).
		Str("text", resp.Data.Body.Text).
		Str("conversationUrn", firstThreadUrn).
		Msg("Successfully sent test image to top conversation")
	os.Exit(1)
}

func testEditMessage() {
	firstThread := getTopThread()
	firstThreadUrn := firstThread.EntityUrn
	firstMessage := firstThread.MessageElements.Messages[0]
	firstMessageUrn := firstMessage.EntityUrn

	newMessageBody := payload.MessageBody{
		Text: "new message content test",
	}
	err := cli.EditMessage(firstMessageUrn, newMessageBody)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().
		Str("thread_id", firstThreadUrn).
		Str("message_id", firstMessageUrn).
		Str("new_text", newMessageBody.Text).
		Str("old_text", firstMessage.Body.Text).
		Msg("Successfully edited message")
	os.Exit(1)
}

// sends a message in the top conversation
func testSendMessage() {
	threads, err := cli.GetThreads(query.GetThreadsVariables{})
	if err != nil {
		log.Fatal(err)
	}

	firstThread := threads.Threads[0]
	firstThreadUrn := firstThread.EntityUrn

	sendMessagePayload := payload.SendMessagePayload{
		Message: payload.SendMessageData{
			Body: payload.MessageBody{
				Text: "testing sending a message",
			},
			ConversationUrn: firstThreadUrn,
		},
		DedupeByClientGeneratedToken: false,
	}

	resp, err := cli.SendMessage(sendMessagePayload)
	if err != nil {
		log.Fatal(err)
	}

	cli.Logger.Info().
		Int64("deliveredAt", resp.Data.DeliveredAt).
		Str("text", resp.Data.Body.Text).
		Str("conversationUrn", firstThreadUrn).
		Msg("Successfully sent test message to top conversation")
	os.Exit(1)
}

func getTopThread() response.ThreadElement {
	threads, err := cli.GetThreads(query.GetThreadsVariables{})
	if err != nil {
		log.Fatal(err)
	}
	return threads.Threads[0]
}*/
