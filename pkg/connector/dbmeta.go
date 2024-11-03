package connector

import (
	"maunium.net/go/mautrix/bridgev2/database"
)

func (lc *LinkedInConnector) GetDBMetaTypes() database.MetaTypes {
	return database.MetaTypes{
		Reaction: nil,
		Portal:   nil,
		Message:  nil,
		Ghost:    nil,
		UserLogin: func() any {
			return &UserLoginMetadata{}
		},
	}
}

type UserLoginMetadata struct {
	Cookies string `json:"cookies"`
}
