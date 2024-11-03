package connector

import (
	"context"
	"fmt"
	"regexp"

	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/database"
	"maunium.net/go/mautrix/bridgev2/networkid"

	"github.com/beeper/linkedin/pkg/linkedingo"
	linCookies "github.com/beeper/linkedin/pkg/linkedingo/cookies"
)

type LinkedInLogin struct {
	User    *bridgev2.User
	Cookies string
	lc      *LinkedInConnector
}

var (
	LoginUrlRegex    = regexp.MustCompile(`https?:\\/\\/(www\\.)?([\\w-]+\\.)*linkedin\\.com(\\/[^\\s]*)?`)
	ValidCookieRegex = regexp.MustCompile(`\bJSESSIONID=[^;]+`)
)

var (
	LoginStepIDCookies  = "fi.mau.linkedin.login.enter_cookies"
	LoginStepIDComplete = "fi.mau.linkedin.login.complete"
)

var _ bridgev2.LoginProcessCookies = (*LinkedInLogin)(nil)

func (lc *LinkedInConnector) GetLoginFlows() []bridgev2.LoginFlow {
	return []bridgev2.LoginFlow{
		{
			Name:        "Cookies",
			Description: "Log in with your LinkedIn account using your cookies",
			ID:          "cookies",
		},
	}
}

func (lc *LinkedInConnector) CreateLogin(_ context.Context, user *bridgev2.User, flowID string) (bridgev2.LoginProcess, error) {
	if flowID != "cookies" {
		return nil, fmt.Errorf("unknown login flow ID: %s", flowID)
	}
	return &LinkedInLogin{User: user, lc: lc}, nil
}

func (l *LinkedInLogin) Start(_ context.Context) (*bridgev2.LoginStep, error) {
	return &bridgev2.LoginStep{
		Type:         bridgev2.LoginStepTypeCookies,
		StepID:       LoginStepIDCookies,
		Instructions: "Open the Login URL in an Incognito/Private browsing mode. Then, extract the Cookie header as a string/cURL command copied from the Network tab of your browser's DevTools. After that, close the browser **before** pasting the header.",
		CookiesParams: &bridgev2.LoginCookiesParams{
			URL:       "https://linkedin.com/login",
			UserAgent: "",
			Fields: []bridgev2.LoginCookieField{
				{
					ID:       "cookie",
					Required: true,
					Sources: []bridgev2.LoginCookieFieldSource{
						{Type: bridgev2.LoginCookieTypeRequestHeader, Name: "Cookie", RequestURLRegex: LoginUrlRegex.String()},
					},
					Pattern: ValidCookieRegex.String(),
				},
			},
		},
	}, nil
}

func (l *LinkedInLogin) Cancel() {}

func (l *LinkedInLogin) SubmitCookies(ctx context.Context, cookies map[string]string) (*bridgev2.LoginStep, error) {
	cookieStruct := linCookies.NewCookiesFromString(cookies["cookie"])

	meta := &UserLoginMetadata{
		Cookies: cookieStruct.String(),
	}

	clientOpts := &linkedingo.ClientOpts{
		Cookies: cookieStruct,
	}
	client := linkedingo.NewClient(clientOpts, l.User.Log)

	err := client.LoadMessagesPage()
	if err != nil {
		return nil, fmt.Errorf("failed to load messages page after submitting cookies")
	}

	profile, err := client.GetCurrentUserProfile()

	id := networkid.UserLoginID(client.GetCurrentUserID())
	ul, err := l.User.NewLogin(
		ctx,
		&database.UserLogin{
			ID:         id,
			Metadata:   meta,
			RemoteName: fmt.Sprintf("%s %s", profile.MiniProfile.FirstName, profile.MiniProfile.LastName),
		},
		&bridgev2.NewLoginParams{
			DeleteOnConflict:  true,
			DontReuseExisting: false,
			LoadUserLogin:     l.lc.LoadUserLogin,
		},
	)
	if err != nil {
		return nil, err
	}

	ul.Client.Connect(ctx)

	return &bridgev2.LoginStep{
		Type:         bridgev2.LoginStepTypeComplete,
		StepID:       LoginStepIDComplete,
		Instructions: fmt.Sprintf("Successfully logged into @%s", ul.UserLogin.RemoteName),
		CompleteParams: &bridgev2.LoginCompleteParams{
			UserLoginID: ul.ID,
			UserLogin:   ul,
		},
	}, nil
}
