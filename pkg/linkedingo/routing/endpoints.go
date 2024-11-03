package routing

const BASE_HOST = "www.linkedin.com"

type RequestEndpointURL string

const (
	BASE_URL                                           RequestEndpointURL = "https://" + BASE_HOST
	MESSAGES_BASE_URL                                  RequestEndpointURL = BASE_URL + "/messaging"
	VOYAGER_GRAPHQL_URL                                                   = BASE_URL + "/voyager/api/graphql"
	VOYAGER_COMMON_ME_URL                                                 = BASE_URL + "/voyager/api/me"
	VOYAGER_MESSAGING_GRAPHQL_URL                                         = BASE_URL + "/voyager/api/voyagerMessagingGraphQL/graphql"
	VOYAGER_MESSAGING_DASH_MESSENGER_MESSAGES_URL                         = BASE_URL + "/voyager/api/voyagerMessagingDashMessengerMessages"
	VOYAGER_MESSAGING_DASH_MESSENGER_CONVERSATIONS_URL                    = BASE_URL + "/voyager/api/voyagerMessagingDashMessengerConversations"
	VOYAGER_MEDIA_UPLOAD_METADATA_URL                                     = BASE_URL + "/voyager/api/voyagerVideoDashMediaUploadMetadata"
	REALTIME_CONNECT_URL                                                  = BASE_URL + "/realtime/connect"
	LOGOUT_URL                                                            = BASE_URL + "/uas/logout"
)
