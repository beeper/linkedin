package query

import (
	"github.com/beeper/linkedin/pkg/linkedingo/methods"
)

type Action string

const (
	ActionCreateMessage    Action = "createMessage"
	ActionTyping           Action = "typing"
	ActionUpload           Action = "upload"
	ActionRecall           Action = "recall"
	ActionReactWithEmoji   Action = "reactWithEmoji"
	ActionUnreactWithEmoji Action = "unreactWithEmoji"
)

type DoActionQuery struct {
	Action Action `url:"action"`
}

func (q DoActionQuery) Encode() ([]byte, error) {
	return []byte("action=" + q.Action), nil
}

type InboxCategory string

const (
	InboxCategoryOther     InboxCategory = "OTHER"
	InboxCategoryArchive   InboxCategory = "ARCHIVE"
	InboxCategoryInbox     InboxCategory = "INBOX"
	InboxCategoryPrimary   InboxCategory = "PRIMARY_INBOX"
	InboxCategorySecondary InboxCategory = "SECONDARY_INBOX"
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
