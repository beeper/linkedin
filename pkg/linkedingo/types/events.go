package types

type RealtimeEvent string

const (
	RealtimeEventClientConnection RealtimeEvent = "com.linkedin.realtimefrontend.ClientConnection"
	RealtimeEventDecoratedEvent   RealtimeEvent = "com.linkedin.realtimefrontend.DecoratedEvent"
	RealtimeEventHeartbeat        RealtimeEvent = "com.linkedin.realtimefrontend.Heartbeat"
)

type RealtimeEventTopic string

const (
	RealtimeEventTopicConversations              RealtimeEventTopic = "conversationsTopic"
	RealtimeEventTopicConversationsDelete        RealtimeEventTopic = "conversationDeletesTopic"
	RealtimeEventTopicMessageSeenReceipts        RealtimeEventTopic = "messageSeenReceiptsTopic"
	RealtimeEventTopicMessages                   RealtimeEventTopic = "messagesTopic"
	RealtimeEventTopicReplySuggestionV2          RealtimeEventTopic = "replySuggestionTopicV2"
	RealtimeEventTopicTabBadgeUpdate             RealtimeEventTopic = "tabBadgeUpdateTopic"
	RealtimeEventTopicTypingIndicators           RealtimeEventTopic = "typingIndicatorsTopic"
	RealtimeEventTopicInvitations                RealtimeEventTopic = "invitationsTopic"
	RealtimeEventTopicInAppAlerts                RealtimeEventTopic = "inAppAlertsTopic"
	RealtimeEventTopicMessageReactionSummaries   RealtimeEventTopic = "messageReactionSummariesTopic"
	RealtimeEventTopicSocialPermissionsPersonal  RealtimeEventTopic = "socialPermissionsPersonalTopic"
	RealtimeEventTopicJobPostingPersonal         RealtimeEventTopic = "jobPostingPersonalTopic"
	RealtimeEventTopicMessagingProgressIndicator RealtimeEventTopic = "messagingProgressIndicatorTopic"
	RealtimeEventTopicMessagingDataSync          RealtimeEventTopic = "messagingDataSyncTopic"
	RealtimeEventTopicPresenceStatus             RealtimeEventTopic = "presenceStatusTopic"
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
	RealtimeEventTypeMessageEvent RealtimeEventType = "com.linkedin.voyager.messaging.event.MessageEvent"
)

type PresenceAvailabilityStatus string

const (
	PresenceAvailabilityStatusOnline  PresenceAvailabilityStatus = "ONLINE"
	PresenceAvailabilityStatusOffline PresenceAvailabilityStatus = "OFFLINE"
)

type ConnectionClosedReason string

const (
	ConnectionClosedReasonSelfDisconnectIssued ConnectionClosedReason = "client called Disconnect() method"
	SecondClosedReasonDropped                  ConnectionClosedReason = "real-time client lost connection to the server"
)
