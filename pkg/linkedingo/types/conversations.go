package types

type ConversationParticipant struct {
	HostIdentityUrn       string          `json:"hostIdentityUrn,omitempty"`
	Preview               any             `json:"preview,omitempty"`
	EntityUrn             string          `json:"entityUrn,omitempty"`
	ShowPremiumInBug      bool            `json:"showPremiumInBug,omitempty"`
	ShowVerificationBadge bool            `json:"showVerificationBadge,omitempty"`
	Type                  string          `json:"_type,omitempty"`
	ParticipantType       ParticipantType `json:"participantType,omitempty"`
	RecipeType            string          `json:"_recipeType,omitempty"`
	BackendUrn            string          `json:"backendUrn,omitempty"`
}

type FirstName struct {
	Type       string `json:"_type,omitempty"`
	Attributes []any  `json:"attributes,omitempty"`
	Text       string `json:"text,omitempty"`
	RecipeType string `json:"_recipeType,omitempty"`
}

type LastName struct {
	Type       string `json:"_type,omitempty"`
	Attributes []any  `json:"attributes,omitempty"`
	Text       string `json:"text,omitempty"`
	RecipeType string `json:"_recipeType,omitempty"`
}

type Headline struct {
	Type       string `json:"_type,omitempty"`
	Attributes []any  `json:"attributes,omitempty"`
	Text       string `json:"text,omitempty"`
	RecipeType string `json:"_recipeType,omitempty"`
}

type Member struct {
	ProfileURL     string         `json:"profileUrl,omitempty"`
	FirstName      FirstName      `json:"firstName,omitempty"`
	LastName       LastName       `json:"lastName,omitempty"`
	ProfilePicture ProfilePicture `json:"profilePicture,omitempty"`
	Distance       string         `json:"distance,omitempty"`
	Pronoun        any            `json:"pronoun,omitempty"`
	Type           string         `json:"_type,omitempty"`
	RecipeType     string         `json:"_recipeType,omitempty"`
	Headline       Headline       `json:"headline,omitempty"`
}

type ParticipantType struct {
	Member       Member `json:"member,omitempty"`
	Custom       any    `json:"custom,omitempty"`
	Organization any    `json:"organization,omitempty"`
}

type ProfilePicture struct {
	RootURL string `json:"rootUrl,omitempty"`
}
