package payload

import "encoding/json"

type GraphQLPatchBody struct {
	Patch Patch `json:"patch,omitempty"`
}

func (p GraphQLPatchBody) Encode() ([]byte, error) {
	return json.Marshal(p)
}

type Set struct {
	Body any `json:"body,omitempty"`
}

type Patch struct {
	Set any `json:"$set,omitempty"`
}

type PatchEntitiesPayload struct {
	Entities map[string]GraphQLPatchBody `json:"entities,omitempty"`
}

func (p PatchEntitiesPayload) Encode() ([]byte, error) {
	return json.Marshal(p)
}
