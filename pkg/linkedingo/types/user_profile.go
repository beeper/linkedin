package types

type UserProfile struct {
	FirstName        string `json:"firstName"`
	LastName         string `json:"lastName"`
	Occupation       string `json:"occupation"`
	PublicIdentifier string `json:"publicIdentifier"`
	Picture          string `json:"picture,omitempty"`
	Memorialized     bool   `json:"memorialized"`

	EntityUrn     string `json:"entityUrn"`
	ObjectUrn     string `json:"objectUrn"`
	DashEntityUrn string `json:"dashEntityUrn"`

	TrackingId string `json:"trackingId"`
}

type UserLoginProfile struct {
	PlainId     int         `json:"plainId"`
	MiniProfile UserProfile `json:"miniProfile"`
}
