package cookies

import (
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

type LinkedInCookieName string

const (
	LinkedInLang                 LinkedInCookieName = "lang"
	LinkedInBCookie              LinkedInCookieName = "bcookie"
	LinkedInBscookie             LinkedInCookieName = "bscookie"
	LinkedInLiAlerts             LinkedInCookieName = "li_alerts"
	LinkedInLiGc                 LinkedInCookieName = "li_gc"
	LinkedInLiRm                 LinkedInCookieName = "li_rm"
	LinkedInGclAu                LinkedInCookieName = "_gcl_au"
	LinkedInAMCVSAdobeOrg        LinkedInCookieName = "AMCVS_14215E3D5995C57C0A495C55%40AdobeOrg" // ???
	LinkedInAamUuid              LinkedInCookieName = "aam_uuid"
	LinkedInLiap                 LinkedInCookieName = "liap"
	LinkedInLiAt                 LinkedInCookieName = "li_at"
	LinkedInJSESSIONID           LinkedInCookieName = "JSESSIONID"
	LinkedInTimezone             LinkedInCookieName = "timezone"
	LinkedInDfpfpt               LinkedInCookieName = "dfpfpt"
	LinkedInFptctx2              LinkedInCookieName = "fptctx2"
	LinkedInAMCVAdobeOrg         LinkedInCookieName = "AMCV_14215E3D5995C57C0A495C55%40AdobeOrg" // ???
	LinkedInLiMc                 LinkedInCookieName = "li_mc"
	LinkedInCfBm                 LinkedInCookieName = "__cf_bm"
	LinkedInLiTheme              LinkedInCookieName = "li_theme"
	LinkedInLiThemeSet           LinkedInCookieName = "li_theme_set"
	LinkedInLiSugr               LinkedInCookieName = "li_sugr"
	LinkedInGuid                 LinkedInCookieName = "_guid"
	LinkedInUserMatchHistory     LinkedInCookieName = "UserMatchHistory"
	LinkedInAnalyticsSyncHistory LinkedInCookieName = "AnalyticsSyncHistory"
	LinkedInLmsAds               LinkedInCookieName = "lms_ads"
	LinkedInLmsAnalytics         LinkedInCookieName = "lms_analytics"
	LinkedInLidc                 LinkedInCookieName = "lidc"
)

type Cookies struct {
	Store map[LinkedInCookieName]string
	lock  sync.RWMutex
}

func NewCookies() *Cookies {
	return &Cookies{
		Store: make(map[LinkedInCookieName]string),
		lock:  sync.RWMutex{},
	}
}

func NewCookiesFromString(cookieStr string) *Cookies {
	c := NewCookies()
	cookieStrings := strings.Split(cookieStr, ";")
	fakeHeader := http.Header{}
	for _, cookieStr := range cookieStrings {
		trimmedCookieStr := strings.TrimSpace(cookieStr)
		if trimmedCookieStr != "" {
			fakeHeader.Add("Set-Cookie", trimmedCookieStr)
		}
	}
	fakeResponse := &http.Response{Header: fakeHeader}

	for _, cookie := range fakeResponse.Cookies() {
		c.Store[LinkedInCookieName(cookie.Name)] = cookie.Value
	}

	return c
}

func (c *Cookies) String() string {
	c.lock.RLock()
	defer c.lock.RUnlock()
	var out []string
	for k, v := range c.Store {
		out = append(out, fmt.Sprintf("%s=%s", k, v))
	}
	return strings.Join(out, "; ")
}

func (c *Cookies) IsCookieEmpty(key LinkedInCookieName) bool {
	return c.Get(key) == ""
}

func (c *Cookies) Get(key LinkedInCookieName) string {
	c.lock.RLock()
	defer c.lock.RUnlock()
	return c.Store[key]
}

func (c *Cookies) Set(key LinkedInCookieName, value string) {
	c.lock.Lock()
	defer c.lock.Unlock()
	c.Store[key] = value
}

func (c *Cookies) UpdateFromResponse(r *http.Response) {
	c.lock.Lock()
	defer c.lock.Unlock()
	for _, cookie := range r.Cookies() {
		if cookie.MaxAge == 0 || cookie.Expires.Before(time.Now()) {
			delete(c.Store, LinkedInCookieName(cookie.Name))
		} else {
			//log.Println(fmt.Sprintf("updated cookie %s to value %s", cookie.Name, cookie.Value))
			c.Store[LinkedInCookieName(cookie.Name)] = cookie.Value
		}
	}
}
