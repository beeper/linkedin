package connector

import (
	"context"

	"maunium.net/go/mautrix/bridgev2"
)

type LinkedInConnector struct {
	br *bridgev2.Bridge

	Config Config
}

var _ bridgev2.NetworkConnector = (*LinkedInConnector)(nil)

func (lc *LinkedInConnector) Init(bridge *bridgev2.Bridge) {
	lc.br = bridge
}

func (lc *LinkedInConnector) Start(_ context.Context) error {
	return nil
}

func (lc *LinkedInConnector) GetName() bridgev2.BridgeName {
	return bridgev2.BridgeName{
		DisplayName:      "LinkedIn",
		NetworkURL:       "https://linkedin.com",
		NetworkIcon:      "mxc://nevarro.space/cwsWnmeMpWSMZLUNblJHaIvP",
		NetworkID:        "linkedin",
		BeeperBridgeType: "linkedin",
		DefaultPort:      29327,
	}
}

func (lc *LinkedInConnector) GetCapabilities() *bridgev2.NetworkGeneralCapabilities {
	return &bridgev2.NetworkGeneralCapabilities{}
}

func (lc *LinkedInConnector) LoadUserLogin(ctx context.Context, login *bridgev2.UserLogin) error {
	twitClient := NewLinkedInClient(ctx, lc, login)

	login.Client = twitClient

	return nil
}
