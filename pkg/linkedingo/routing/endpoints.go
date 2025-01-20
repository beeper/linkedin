package routing

const LinkedInBaseHost = "www.linkedin.com"

type RequestEndpointURL string

const (
	LinkedInBaseURL                                  RequestEndpointURL = "https://" + LinkedInBaseHost
	LinkedInMessagingBaseURL                                            = LinkedInBaseURL + "/messaging"
	LinkedInVoyagerGraphQLURL                                           = LinkedInBaseURL + "/voyager/api/graphql"
	LinkedInVoyagerCommonMeURL                                          = LinkedInBaseURL + "/voyager/api/me"
	LinkedInVoyagerMessagingGraphQLURL                                  = LinkedInBaseURL + "/voyager/api/voyagerMessagingGraphQL/graphql"
	LinkedInVoyagerMessagingDashMessengerMessagesURL                    = LinkedInBaseURL + "/voyager/api/voyagerMessagingDashMessengerMessages"
	LinkedInMessagingDashMessengerConversationsURL                      = LinkedInBaseURL + "/voyager/api/voyagerMessagingDashMessengerConversations"
	LinkedInVoyagerMediaUploadMetadataURL                               = LinkedInBaseURL + "/voyager/api/voyagerVideoDashMediaUploadMetadata"
	LinkedInRealtimeConnectURL                                          = LinkedInBaseURL + "/realtime/connect"
	LinkedInLogoutURL                                                   = LinkedInBaseURL + "/uas/logout"
)
