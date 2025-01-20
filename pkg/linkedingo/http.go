package linkedingo

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/beeper/linkedin/pkg/linkedingo/routing"
	"github.com/beeper/linkedin/pkg/linkedingo/types"
)

const MaxHTTPRetries = 5

var (
	ErrRedirectAttempted  = errors.New("redirect attempted")
	ErrTokenInvalidated   = errors.New("access token is no longer valid")
	ErrChallengeRequired  = errors.New("challenge required")
	ErrConsentRequired    = errors.New("consent required")
	ErrAccountSuspended   = errors.New("account suspended")
	ErrRequestFailed      = errors.New("failed to send request")
	ErrResponseReadFailed = errors.New("failed to read response body")
	ErrMaxRetriesReached  = errors.New("maximum retries reached")
)

func isPermanentRequestError(err error) bool {
	return errors.Is(err, ErrTokenInvalidated) ||
		errors.Is(err, ErrChallengeRequired) ||
		errors.Is(err, ErrConsentRequired) ||
		errors.Is(err, ErrAccountSuspended)
}

func (c *Client) MakeRoutingRequest(endpointURL routing.RequestEndpointURL, payload routing.PayloadDataInterface, query routing.PayloadDataInterface) (*http.Response, any, error) {
	routingDefinition, ok := routing.RequestStoreDefinition[endpointURL]
	if !ok {
		return nil, nil, fmt.Errorf("failed to find request definition for endpointURL %s", string(endpointURL))
	}

	headers := c.buildHeaders(routingDefinition.HeaderOpts)
	url := string(endpointURL)

	if query != nil {
		encodedQuery, err := query.Encode()
		if err != nil {
			return nil, nil, err
		}
		url = url + "?" + string(encodedQuery)
	}

	var payloadBytes []byte
	if payload != nil {
		encodedPayload, err := payload.Encode()
		if err != nil {
			return nil, nil, err
		}
		payloadBytes = encodedPayload
	}

	resp, respBody, err := c.MakeRequest(url, routingDefinition.Method, headers, payloadBytes, routingDefinition.ContentType)
	if err != nil {
		return nil, nil, err
	}

	respDefinition := routingDefinition.ResponseDefinition
	var respStruct any
	if respDefinition != nil && len(respBody) > 0 {
		respStruct, err = respDefinition.Decode(respBody)
	}

	return resp, respStruct, err
}

func (c *Client) MakeRequest(url string, method string, headers http.Header, payload []byte, contentType types.ContentType) (*http.Response, []byte, error) {
	var attempts int
	for {
		attempts++
		start := time.Now()
		resp, respDat, err := c.makeRequestDirect(url, method, headers, payload, contentType)
		dur := time.Since(start)
		if err == nil {
			c.Logger.Debug().
				Str("url", url).
				Str("method", method).
				Dur("duration", dur).
				Msg("Request successful")
			return resp, respDat, nil
		} else if attempts > MaxHTTPRetries {
			c.Logger.Err(err).
				Str("url", url).
				Str("method", method).
				Dur("duration", dur).
				Msg("Request failed, giving up")
			return nil, nil, fmt.Errorf("%w: %w", ErrMaxRetriesReached, err)
		} else if isPermanentRequestError(err) {
			c.Logger.Err(err).
				Str("url", url).
				Str("method", method).
				Dur("duration", dur).
				Msg("Request failed, cannot be retried")
			return nil, nil, err
		} else if errors.Is(err, ErrRedirectAttempted) {
			location := resp.Header.Get("Location")
			c.Logger.Err(err).
				Str("url", url).
				Str("location", location).
				Str("method", method).
				Dur("duration", dur).
				Msg("Redirect attempted")
			return resp, nil, err
		}
		c.Logger.Err(err).
			Str("url", url).
			Str("method", method).
			Dur("duration", dur).
			Msg("Request failed, retrying")
		time.Sleep(time.Duration(attempts) * 3 * time.Second)
	}
}

func (c *Client) makeRequestDirect(url string, method string, headers http.Header, payload []byte, contentType types.ContentType) (*http.Response, []byte, error) {
	newRequest, err := http.NewRequest(method, url, bytes.NewBuffer(payload))
	if err != nil {
		return nil, nil, err
	}

	if contentType != "" {
		headers.Set("content-type", string(contentType))
	}

	newRequest.Header = headers

	response, err := c.http.Do(newRequest)
	defer func() {
		if response != nil && response.Body != nil {
			_ = response.Body.Close()
		}
	}()
	if err != nil {
		if errors.Is(err, ErrRedirectAttempted) {
			return response, nil, err
		}
		c.Logger.Warn().Str("error", err.Error()).Msg("Http request error")
		// c.UpdateProxy(fmt.Sprintf("http request error: %v", err.Error()))
		return nil, nil, fmt.Errorf("%w: %w", ErrRequestFailed, err)
	}

	responseBody, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, nil, fmt.Errorf("%w: %w", ErrResponseReadFailed, err)
	}

	return response, responseBody, nil
}
