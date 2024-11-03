package linkedingo

import "fmt"

func newErrorResponseTypeAssertFailed(t string) error {
	return fmt.Errorf("failed to type assert response from routing request into %s", t)
}
