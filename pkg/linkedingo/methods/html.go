package methods

import (
	"fmt"
	"regexp"
)

var (
	MetaTagRegex    = `<meta\s+name="%s"\s+content="([^"]+)"\s*?>`
	FsdProfileRegex = regexp.MustCompile(`urn:li:fsd_profile:[A-Za-z0-9]*-sub0`)
)

func ParseMetaTagValue(html string, name string) string {
	metaRegexp := regexp.MustCompile(fmt.Sprintf(MetaTagRegex, name))
	matches := metaRegexp.FindStringSubmatch(html)
	if len(matches) < 2 {
		return ""
	}

	return matches[1]
}

func ParseFsdProfileID(html string) string {
	matches := FsdProfileRegex.FindStringSubmatch(html)
	if len(matches) < 1 {
		return ""
	}

	return matches[0]
}
