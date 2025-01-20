package main

import (
	"net/http"

	"maunium.net/go/mautrix/bridgev2/bridgeconfig"
	"maunium.net/go/mautrix/bridgev2/matrix/mxmain"

	"github.com/beeper/linkedin/pkg/connector"
)

// Information to find out exactly which commit the bridge was built from.
// These are filled at build time with the -X linker flag.
var (
	Tag       = "unknown"
	Commit    = "unknown"
	BuildTime = "unknown"
)

var m = mxmain.BridgeMain{
	Name:        "linkedin-matrix",
	URL:         "https://github.com/beeper/linkedin",
	Description: "A Matrix-LinkedIn puppeting bridge.",
	Version:     "0.6.0",
	Connector:   &connector.LinkedInConnector{},
}

func main() {
	bridgeconfig.HackyMigrateLegacyNetworkConfig = migrateLegacyConfig
	m.PostStart = func() {
		if m.Matrix.Provisioning != nil {
			m.Matrix.Provisioning.Router.HandleFunc("/v1/api/whoami", legacyProvStatus).Methods(http.MethodGet)
			m.Matrix.Provisioning.Router.HandleFunc("/v1/api/login", legacyProvLogin).Methods(http.MethodPost)
			m.Matrix.Provisioning.Router.HandleFunc("/v1/api/logout", legacyProvLogout).Methods(http.MethodPost)
		}
	}

	m.InitVersion(Tag, Commit, BuildTime)
	m.Run()
}
