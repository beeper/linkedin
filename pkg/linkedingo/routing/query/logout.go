package query

import (
	"github.com/google/go-querystring/query"
)

type LogoutQuery struct {
	CsrfToken string `url:"csrfToken"`
}

func (p *LogoutQuery) Encode() ([]byte, error) {
	values, err := query.Values(p)
	if err != nil {
		return nil, err
	}
	return []byte(values.Encode()), nil
}
