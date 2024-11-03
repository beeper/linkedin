package methods

import (
	"fmt"
	"net/url"
	"reflect"
	"strings"

	"go.mau.fi/util/random"
)

// this works btw, just doesn't include invalid bytes
// return string(random.StringBytes(16))
func GenerateTrackingId() string {
	randByteArray := random.Bytes(16)
	charArray := make([]rune, len(randByteArray))
	for i, b := range randByteArray {
		charArray[i] = rune(b)
	}
	return string(charArray)
}

func EncodeGraphQLQuery(definition any) ([]byte, error) {
	var sb strings.Builder
	sb.WriteString("(")

	v := reflect.ValueOf(definition)
	t := v.Type()

	firstField := true

	for i := 0; i < v.NumField(); i++ {
		fieldValue := v.Field(i).Interface()
		fieldType := t.Field(i)
		if !isZeroValue(fieldValue) {
			if !firstField {
				sb.WriteString(",")
			}
			firstField = false
			graphQlTagName := fieldType.Tag.Get("graphql")
			sb.WriteString(fmt.Sprintf("%s:%s", graphQlTagName, url.QueryEscape(fmt.Sprintf("%v", fieldValue))))
		}
	}

	sb.WriteString(")")
	return []byte(sb.String()), nil
}

func isZeroValue(value any) bool {
	switch v := value.(type) {
	case int, int8, int16, int32, int64:
		return v == 0
	case uint, uint8, uint16, uint32, uint64:
		return v == 0
	case float32, float64:
		return v == 0
	case string:
		return v == ""
	case bool:
		return !v
	default:
		return reflect.DeepEqual(value, reflect.Zero(reflect.TypeOf(value)).Interface())
	}
}
