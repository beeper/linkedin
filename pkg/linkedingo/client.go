package linkedingo

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"time"

	"github.com/rs/zerolog"
	"golang.org/x/net/proxy"

	"github.com/beeper/linkedin/pkg/linkedingo/cookies"
	"github.com/beeper/linkedin/pkg/linkedingo/routing"
	queryData "github.com/beeper/linkedin/pkg/linkedingo/routing/query"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type EventHandler func(evt any)
type ClientOpts struct {
	Cookies      *cookies.Cookies
	EventHandler EventHandler
}
type Client struct {
	Logger       zerolog.Logger
	cookies      *cookies.Cookies
	pageLoader   *PageLoader
	rc           *RealtimeClient
	http         *http.Client
	httpProxy    func(*http.Request) (*url.URL, error)
	socksProxy   proxy.Dialer
	eventHandler EventHandler
}

func NewClient(opts *ClientOpts, logger zerolog.Logger) *Client {
	cli := Client{
		http: &http.Client{
			Transport: &http.Transport{
				DialContext:           (&net.Dialer{Timeout: 10 * time.Second}).DialContext,
				TLSHandshakeTimeout:   10 * time.Second,
				ResponseHeaderTimeout: 40 * time.Second,
				ForceAttemptHTTP2:     true,
			},
			Timeout: 60 * time.Second,
		},
		Logger: logger,
	}

	if opts.EventHandler != nil {
		cli.SetEventHandler(opts.EventHandler)
	}

	if opts.Cookies != nil {
		cli.cookies = opts.Cookies
	} else {
		cli.cookies = cookies.NewCookies()
	}

	cli.rc = cli.newRealtimeClient()
	cli.pageLoader = cli.newPageLoader()

	return &cli
}

func (c *Client) Connect() error {
	return c.rc.Connect()
}

func (c *Client) Disconnect() error {
	return c.rc.Disconnect()
}

func (c *Client) Logout() error {
	query := queryData.LogoutQuery{
		CsrfToken: c.cookies.Get(cookies.LinkedInJSESSIONID),
	}
	encodedQuery, err := query.Encode()
	if err != nil {
		return err
	}

	logoutUrl := fmt.Sprintf("%s?%s", routing.LinkedInLogoutURL, string(encodedQuery))

	logoutDefinition := routing.RequestStoreDefinition[routing.LinkedInLogoutURL]
	headers := c.buildHeaders(logoutDefinition.HeaderOpts)
	_, _, err = c.MakeRequest(logoutUrl, http.MethodGet, headers, nil, logoutDefinition.ContentType)
	_ = c.Disconnect()
	c.cookies.Store = make(map[cookies.LinkedInCookieName]string)
	return err
}

func (c *Client) GetCookieString() string {
	return c.cookies.String()
}

func (c *Client) LoadMessagesPage() error {
	return c.pageLoader.LoadMessagesPage()
}

func (c *Client) GetCurrentUserID() string {
	return c.pageLoader.CurrentUser.FsdProfileID
}

func (c *Client) GetCurrentUserProfile() (*types.UserLoginProfile, error) {
	headers := c.buildHeaders(types.HeaderOpts{
		WithCookies:         true,
		WithCsrfToken:       true,
		WithXLiTrack:        true,
		WithXLiPageInstance: true,
		WithXLiProtocolVer:  true,
		WithXLiLang:         true,
	})

	_, data, err := c.MakeRequest(string(routing.LinkedInVoyagerCommonMeURL), http.MethodGet, headers, make([]byte, 0), types.ContentTypeJSONLinkedInNormalized)
	if err != nil {
		return nil, err
	}

	response := &types.UserLoginProfile{}

	err = json.Unmarshal(data, response)
	if err != nil {
		return nil, err
	}

	return response, nil
}

func (c *Client) SetProxy(proxyAddr string) error {
	proxyParsed, err := url.Parse(proxyAddr)
	if err != nil {
		return err
	}

	if proxyParsed.Scheme == "http" || proxyParsed.Scheme == "https" {
		c.httpProxy = http.ProxyURL(proxyParsed)
		c.http.Transport.(*http.Transport).Proxy = c.httpProxy
	} else if proxyParsed.Scheme == "socks5" {
		c.socksProxy, err = proxy.FromURL(proxyParsed, &net.Dialer{Timeout: 20 * time.Second})
		if err != nil {
			return err
		}
		c.http.Transport.(*http.Transport).DialContext = func(ctx context.Context, network string, addr string) (net.Conn, error) {
			return c.socksProxy.Dial(network, addr)
		}
		contextDialer, ok := c.socksProxy.(proxy.ContextDialer)
		if ok {
			c.http.Transport.(*http.Transport).DialContext = contextDialer.DialContext
		}
	}

	c.Logger.Debug().
		Str("scheme", proxyParsed.Scheme).
		Str("host", proxyParsed.Host).
		Msg("Using proxy")
	return nil
}

func (c *Client) SetEventHandler(handler EventHandler) {
	c.eventHandler = handler
}
