package query

import (
	"fmt"

	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

type GraphQLQuery struct {
	IncludeWebMetadata bool                  `url:"includeWebMetadata,omitempty"`
	QueryID            types.GraphQLQueryIDs `url:"queryId,omitempty"`
	Variables          string                `url:"variables,omitempty"`
}

func (q *GraphQLQuery) Encode() ([]byte, error) {
	return []byte(fmt.Sprintf("queryId=%s&variables=%s", q.QueryID, q.Variables)), nil
}
