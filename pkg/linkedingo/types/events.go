package types

type RealtimeEvent string

const (
	ClientConnectionEvent RealtimeEvent = "com.linkedin.realtimefrontend.ClientConnection"
	DecoratedEvent        RealtimeEvent = "com.linkedin.realtimefrontend.DecoratedEvent"
	HeartBeat             RealtimeEvent = "com.linkedin.realtimefrontend.Heartbeat"
)

type RealtimeEventTopic string

const (
	ConversationsTopic              RealtimeEventTopic = "conversationsTopic"
	ConversationsDeleteTopic        RealtimeEventTopic = "conversationDeletesTopic"
	MessageSeenReceiptsTopic        RealtimeEventTopic = "messageSeenReceiptsTopic"
	MessagesTopic                   RealtimeEventTopic = "messagesTopic"
	ReplySuggestionTopicV2          RealtimeEventTopic = "replySuggestionTopicV2"
	TabBadgeUpdateTopic             RealtimeEventTopic = "tabBadgeUpdateTopic"
	TypingIndicatorsTopic           RealtimeEventTopic = "typingIndicatorsTopic"
	InvitationsTopic                RealtimeEventTopic = "invitationsTopic"
	InAppAlertsTopic                RealtimeEventTopic = "inAppAlertsTopic"
	MessageReactionSummariesTopic   RealtimeEventTopic = "messageReactionSummariesTopic"
	SocialPermissionsPersonalTopic  RealtimeEventTopic = "socialPermissionsPersonalTopic"
	JobPostingPersonalTopic         RealtimeEventTopic = "jobPostingPersonalTopic"
	MessagingProgressIndicatorTopic RealtimeEventTopic = "messagingProgressIndicatorTopic"
	MessagingDataSyncTopic          RealtimeEventTopic = "messagingDataSyncTopic"
	PresenceStatusTopic             RealtimeEventTopic = "presenceStatusTopic"
)

type LinkedInAPIType string

const (
	MiniProfile     LinkedInAPIType = "com.linkedin.voyager.identity.shared.MiniProfile"
	Conversation    LinkedInAPIType = "com.linkedin.voyager.messaging.Conversation"
	MessagingMember LinkedInAPIType = "com.linkedin.voyager.messaging.MessagingMember"
	Event           LinkedInAPIType = "com.linkedin.voyager.messaging.Event"
)

type RealtimeEventType string

const (
	MessageEvent RealtimeEventType = "com.linkedin.voyager.messaging.event.MessageEvent"
)

type PresenceAvailabilityStatus string

const (
	Online  PresenceAvailabilityStatus = "ONLINE"
	Offline PresenceAvailabilityStatus = "OFFLINE"
)

type ConnectionClosedReason string

const (
	SELF_DISCONNECT_ISSUED ConnectionClosedReason = "client called Disconnect() method"
	CONNECTION_DROPPED     ConnectionClosedReason = "real-time client lost connection to the server"
)
