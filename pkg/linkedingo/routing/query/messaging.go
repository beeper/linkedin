package query

import (
	"github.com/beeper/linkedin/pkg/linkedingo/methods"
)

type Action string

const (
	ACTION_CREATE_MESSAGE     Action = "createMessage"
	ACTION_TYPING             Action = "typing"
	ACTION_UPLOAD             Action = "upload"
	ACTION_RECALL             Action = "recall"
	ACTION_REACT_WITH_EMOJI   Action = "reactWithEmoji"
	ACTION_UNREACT_WITH_EMOJI Action = "unreactWithEmoji"
)

type DoActionQuery struct {
	Action Action `url:"action"`
}

func (q DoActionQuery) Encode() ([]byte, error) {
	return []byte("action=" + q.Action), nil
}

type InboxCategory string

const (
	INBOX_CATEGORY_OTHER     InboxCategory = "OTHER"
	INBOX_CATEGORY_ARCHIVE   InboxCategory = "ARCHIVE"
	INBOX_CATEGORY_INBOX     InboxCategory = "INBOX"
	INBOX_CATEGORY_PRIMARY   InboxCategory = "PRIMARY_INBOX"
	INBOX_CATEGORY_SECONDARY InboxCategory = "SECONDARY_INBOX"
)

type GetThreadsVariables struct {
	InboxCategory     InboxCategory `graphql:"category"`
	Count             int64         `graphql:"count"`
	MailboxUrn        string        `graphql:"mailboxUrn"`
	LastUpdatedBefore int64         `graphql:"lastUpdatedBefore"`
	NextCursor        string        `graphql:"nextCursor"`
	SyncToken         string        `graphql:"syncToken"`
}

func (q GetThreadsVariables) Encode() ([]byte, error) {
	return methods.EncodeGraphQLQuery(q)
}

type FetchMessagesVariables struct {
	DeliveredAt     int64  `graphql:"deliveredAt"`
	ConversationUrn string `graphql:"conversationUrn"`
	Count           int64  `graphql:"count"`
	PrevCursor      string `graphql:"prevCursor"`
	CountBefore     int64  `graphql:"countBefore"`
	CountAfter      int64  `graphql:"countAfter"`
}

func (q FetchMessagesVariables) Encode() ([]byte, error) {
	return methods.EncodeGraphQLQuery(q)
}

type GetReactionsForEmojiVariables struct {
	Emoji      string `graphql:"emoji"`
	MessageUrn string `graphql:"messageUrn"`
}

func (q GetReactionsForEmojiVariables) Encode() ([]byte, error) {
	return methods.EncodeGraphQLQuery(q)
}
