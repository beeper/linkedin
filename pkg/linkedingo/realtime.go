package linkedingo

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/beeper/linkedin/pkg/linkedingo/event"
	"github.com/beeper/linkedin/pkg/linkedingo/event/raw"
	"github.com/beeper/linkedin/pkg/linkedingo/routing"
	"github.com/beeper/linkedin/pkg/linkedingo/routing/response"
	"github.com/beeper/linkedin/pkg/linkedingo/types"

	"github.com/google/uuid"
)

type RealtimeClient struct {
	client     *Client
	http       *http.Client
	conn       *http.Response
	cancelFunc context.CancelFunc
	sessionID  string
}

func (c *Client) newRealtimeClient() *RealtimeClient {
	return &RealtimeClient{
		client: c,
		http: &http.Client{
			Transport: &http.Transport{
				Proxy: c.httpProxy,
			},
		},
		sessionID: uuid.NewString(),
	}
}

func (rc *RealtimeClient) Connect() error {
	extraHeaders := map[string]string{
		"accept":                string(types.TEXT_EVENTSTREAM),
		"x-li-realtime-session": rc.sessionID,
		"x-li-recipe-accept":    string(types.JSON_LINKEDIN_NORMALIZED),
		"x-li-query-accept":     string(types.GRAPHQL),
		"x-li-accept":           string(types.JSON_LINKEDIN_NORMALIZED),
		"x-li-recipe-map":       `{"inAppAlertsTopic":"com.linkedin.voyager.dash.deco.identity.notifications.InAppAlert-51","professionalEventsTopic":"com.linkedin.voyager.dash.deco.events.ProfessionalEventDetailPage-57","topCardLiveVideoTopic":"com.linkedin.voyager.dash.deco.video.TopCardLiveVideo-9","tabBadgeUpdateTopic":"com.linkedin.voyager.dash.deco.notifications.RealtimeBadgingItemCountsEvent-1"}`,
		"x-li-query-map":        `{"topicToGraphQLQueryParams":{"conversationsBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.dc0088938e4fd0220c7694cdc1e7e2f6","variables":{},"extensions":{}},"conversationsTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.dc0088938e4fd0220c7694cdc1e7e2f6","variables":{},"extensions":{}},"conversationDeletesBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.282abe5fa1a242cb76825c32dbbfaede","variables":{},"extensions":{}},"conversationDeletesTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.282abe5fa1a242cb76825c32dbbfaede","variables":{},"extensions":{}},"messageReactionSummariesBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.3173250b03ea4f9f9e138a145cf3d9b4","variables":{},"extensions":{}},"messageReactionSummariesTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.3173250b03ea4f9f9e138a145cf3d9b4","variables":{},"extensions":{}},"messageSeenReceiptsBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.56fd79ca10248ead05369fa7ab1868dc","variables":{},"extensions":{}},"messageSeenReceiptsTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.56fd79ca10248ead05369fa7ab1868dc","variables":{},"extensions":{}},"messagesBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.9a690a85b608d1212fdaed40be3a1465","variables":{},"extensions":{}},"messagesTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.9a690a85b608d1212fdaed40be3a1465","variables":{},"extensions":{}},"replySuggestionBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.412964c3f7f5a67fb0e56b6bb3a00028","variables":{},"extensions":{}},"replySuggestionTopicV2":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.412964c3f7f5a67fb0e56b6bb3a00028","variables":{},"extensions":{}},"typingIndicatorsBroadcastTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.ad2174343a09cd7ef53b2e6f633695fe","variables":{},"extensions":{}},"typingIndicatorsTopic":{"queryId":"voyagerMessagingDashMessengerRealtimeDecoration.ad2174343a09cd7ef53b2e6f633695fe","variables":{},"extensions":{}},"messagingSecondaryPreviewBannerTopic":{"queryId":"voyagerMessagingDashRealtimeDecoration.60068248c1f5c683ad2557f7ccfdf188","variables":{},"extensions":{}},"reactionsTopic":{"queryId":"liveVideoVoyagerSocialDashRealtimeDecoration.b8b33dedca7efbe34f1d7e84c3b3aa81","variables":{},"extensions":{}},"commentsTopic":{"queryId":"liveVideoVoyagerSocialDashRealtimeDecoration.c582028e0b04485c17e4324d3f463e11","variables":{},"extensions":{}},"reactionsOnCommentsTopic":{"queryId":"liveVideoVoyagerSocialDashRealtimeDecoration.0a181b05b3751f72ae3eb489b77e3245","variables":{},"extensions":{}},"socialPermissionsPersonalTopic":{"queryId":"liveVideoVoyagerSocialDashRealtimeDecoration.170bf3bfbcca1da322e34f34f37fb954","variables":{},"extensions":{}},"liveVideoPostTopic":{"queryId":"liveVideoVoyagerFeedDashLiveUpdatesRealtimeDecoration.ccc245beb0ba0d99bd1df96a1fc53abc","variables":{},"extensions":{}},"generatedJobDescriptionsTopic":{"queryId":"voyagerHiringDashRealtimeDecoration.58501bc70ea8ce6b858527fb1be95007","variables":{},"extensions":{}},"eventToastsTopic":{"queryId":"voyagerEventsDashProfessionalEventsRealtimeResource.6b42abd3511e267e84a6765257deea50","variables":{},"extensions":{}},"coachStreamingResponsesTopic":{"queryId":"voyagerCoachDashGaiRealtimeDecoration.c5707587cf5d95191185235cf15d5129","variables":{},"extensions":{}},"realtimeSearchResultClustersTopic":{"queryId":"voyagerSearchDashRealtimeDecoration.545edd9da8c728b0854505ab6df11870","variables":{},"extensions":{}}}}`,
	}
	headerOpts := types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		WithXLiTrack:        true,
		WithXLiPageInstance: true,
		WithXLiProtocolVer:  true,
		Extra:               extraHeaders,
		Referer:             string(routing.MESSAGES_BASE_URL) + "/",
	}
	headers := rc.client.buildHeaders(headerOpts)

	ctx, cancel := context.WithCancel(context.Background())
	rc.cancelFunc = cancel

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, string(routing.REALTIME_CONNECT_URL)+"?rc=1", nil) // ("GET", string(routing.REALTIME_CONNECT_URL) + "?rc=1", nil)
	if err != nil {
		return err
	}
	req.Header = headers

	conn, err := rc.http.Do(req)
	if err != nil {
		return err
	}

	if conn.StatusCode != http.StatusOK {
		return fmt.Errorf("bad status: %s", conn.Status)
	}

	rc.conn = conn
	go rc.beginReadStream()

	return nil
}

func (rc *RealtimeClient) beginReadStream() {
	reader := bufio.NewReader(rc.conn.Body)
	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			if errors.Is(err, context.Canceled) { // currently only means that Disconnect() was called
				break
			}
			log.Fatalf("error reading from event stream: %s", err.Error())
		}

		line = strings.TrimSpace(line)
		if len(line) == 0 {
			continue
		}

		if strings.HasPrefix(line, "data: ") {
			eventDataString := strings.TrimPrefix(line, "data: ")
			var eventData map[types.RealtimeEvent]json.RawMessage
			err = json.Unmarshal([]byte(eventDataString), &eventData)
			if err != nil {
				log.Printf("error unmarshaling JSON event data: %v\n", err)
				continue
			}

			rc.processEvents(eventData)
		}
	}
}

func (rc *RealtimeClient) Disconnect() error {
	if rc.conn == nil {
		return fmt.Errorf("realtime client is not connected yet")
	}

	if rc.cancelFunc == nil {
		return fmt.Errorf("cancel func is somehow nil, can not disconnect real-time client")
	}

	rc.cancelFunc()

	rc.conn = nil
	rc.cancelFunc = nil
	rc.sessionID = uuid.NewString()

	if rc.client.eventHandler != nil {
		rc.client.eventHandler(event.ConnectionClosed{
			Reason: types.SELF_DISCONNECT_ISSUED,
		})
	}

	return nil
}

func (rc *RealtimeClient) processEvents(data map[types.RealtimeEvent]json.RawMessage) {
	for eventType, eventDataBytes := range data {
		switch eventType {
		case types.DecoratedEvent:
			var decoratedEventResponse raw.DecoratedEventResponse
			err := json.Unmarshal(eventDataBytes, &decoratedEventResponse)
			if err != nil {
				log.Fatalf("failed to unmarshal event bytes with type %s into raw.DecoratedEventResponse", eventType)
			}
			log.Println(string(eventDataBytes))
			rc.processDecoratedEvent(decoratedEventResponse)
		case types.HeartBeat:
			log.Println("received heartbeat")
		case types.ClientConnectionEvent:
			if rc.client.eventHandler != nil {
				rc.client.eventHandler(event.ConnectionReady{})
			}
		default:
			rc.client.Logger.Warn().Str("json_data", string(eventDataBytes)).Str("event_type", string(eventType)).Msg("Received unknown event")
		}
	}
}

func (rc *RealtimeClient) processDecoratedEvent(data raw.DecoratedEventResponse) {
	var evtData any
	topic, topicChunks := parseRealtimeTopic(data.Topic)
	switch topic {
	case types.MessagesTopic:
		renderFormat := data.Payload.Data.DecoratedMessage.Result.MessageBodyRenderFormat
		switch renderFormat {
		case response.RenderFormatDefault:
			evtData = data.Payload.Data.ToMessageEvent()
		case response.RenderFormatEdited:
			evtData = data.Payload.Data.ToMessageEditedEvent()
		case response.RenderFormatReCalled:
			evtData = data.Payload.Data.ToMessageDeleteEvent()
		case response.RenderFormatSystem:
			evtData = data.Payload.Data.ToSystemMessageEvent()
		default:
			rc.client.Logger.Warn().Any("json_data", data.Payload).Str("format", string(renderFormat)).Msg("Received unknown message body render format")
		}
	case types.MessageReactionSummariesTopic:
		evtData = data.Payload.Data.ToMessageReactionEvent()
	case types.TypingIndicatorsTopic:
		evtData = data.Payload.Data.ToTypingIndicatorEvent()
	case types.PresenceStatusTopic:
		fsdProfileId := topicChunks[:-0]
		log.Println("presence updated for user id:", fsdProfileId)
		evtData = data.Payload.ToPresenceStatusUpdateEvent(fsdProfileId[0])
	case types.MessageSeenReceiptsTopic:
		evtData = data.Payload.Data.ToMessageSeenEvent()
	case types.ConversationsTopic:
		evtData = data.Payload.Data.ToThreadUpdateEvent()
	case types.ConversationsDeleteTopic:
		evtData = data.Payload.Data.ToThreadDeleteEvent()
	/* Ignored event topics */
	case types.JobPostingPersonalTopic:
	case types.SocialPermissionsPersonalTopic:
	case types.MessagingProgressIndicatorTopic:
	case types.MessagingDataSyncTopic:
	case types.InvitationsTopic:
	case types.InAppAlertsTopic:
	case types.ReplySuggestionTopicV2:
	case types.TabBadgeUpdateTopic:
		break
	default:
		rc.client.Logger.Warn().Any("json_data", data.Payload).Str("event_topic", string(data.Topic)).Msg("Received unknown event topic")
	}

	if evtData != nil {
		rc.client.eventHandler(evtData)
	}
}

func parseRealtimeTopic(topic string) (types.RealtimeEventTopic, []string) {
	topicChunks := strings.Split(topic, ":")
	return types.RealtimeEventTopic(topicChunks[2]), topicChunks
}
