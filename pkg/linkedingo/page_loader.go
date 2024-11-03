package linkedingo

import (
	"fmt"
	"net/url"

	"github.com/beeper/linkedin/pkg/linkedingo/methods"
	"github.com/beeper/linkedin/pkg/linkedingo/routing"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type CurrentUser struct {
	FsdProfileID string
}

func (u *CurrentUser) GetEncodedFsdID() string {
	return url.QueryEscape(u.FsdProfileID)
}

type PageLoader struct {
	client          *Client
	CurrentUser     *CurrentUser
	XLiDeviceTrack  *types.DeviceTrack
	XLiPageInstance string
	XLiLang         string
}

func (c *Client) newPageLoader() *PageLoader {
	return &PageLoader{
		client:      c,
		CurrentUser: &CurrentUser{},
	}
}

func (pl *PageLoader) LoadMessagesPage() error {
	messagesDefinition := routing.RequestStoreDefinition[routing.MESSAGES_BASE_URL]
	headers := pl.client.buildHeaders(messagesDefinition.HeaderOpts)
	_, respBody, err := pl.client.MakeRequest(string(routing.MESSAGES_BASE_URL), string(messagesDefinition.Method), headers, nil, types.NONE)
	if err != nil {
		return err
	}

	mainPageHTML := string(respBody)

	pl.XLiDeviceTrack = pl.ParseDeviceTrackInfo(mainPageHTML)
	pl.XLiPageInstance = pl.ParseXLiPageInstance(mainPageHTML)
	pl.XLiLang = methods.ParseMetaTagValue(mainPageHTML, "i18nLocale")

	fsdProfileId := methods.ParseFsdProfileID(mainPageHTML)
	if fsdProfileId == "" {
		return fmt.Errorf("failed to find current user fsd profile id in html response to messaging page")
	}

	pl.CurrentUser.FsdProfileID = fsdProfileId

	return nil
}

func (pl *PageLoader) ParseDeviceTrackInfo(html string) *types.DeviceTrack {
	serviceVersion := methods.ParseMetaTagValue(html, "serviceVersion")
	return &types.DeviceTrack{
		ClientVersion:    serviceVersion,
		MpVersion:        serviceVersion,
		OsName:           "web",
		TimezoneOffset:   2,
		Timezone:         "Europe/Stockholm", // TODO scrutinize?
		DeviceFormFactor: "DESKTOP",
		MpName:           "voyager-web",
		DisplayDensity:   1.125,
		DisplayWidth:     2560.5,
		DisplayHeight:    1440,
	}
}

func (pl *PageLoader) ParseXLiPageInstance(html string) string {
	clientPageInstanceId := methods.ParseMetaTagValue(html, "clientPageInstanceId")
	return "urn:li:page:messaging_index;" + clientPageInstanceId
}
