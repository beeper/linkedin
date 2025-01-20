package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

	"github.com/rs/zerolog"
	"go.mau.fi/util/exhttp"
	"maunium.net/go/mautrix"
	"maunium.net/go/mautrix/bridge/status"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/bridgeconfig"

	"github.com/beeper/linkedin/pkg/connector"
)

var levelsToNames = map[bridgeconfig.Permissions]string{
	bridgeconfig.PermissionLevelBlock:    "block",
	bridgeconfig.PermissionLevelRelay:    "relay",
	bridgeconfig.PermissionLevelCommands: "commands",
	bridgeconfig.PermissionLevelUser:     "user",
	bridgeconfig.PermissionLevelAdmin:    "admin",
}

func legacyProvStatus(w http.ResponseWriter, r *http.Request) {
	user := m.Matrix.Provisioning.GetUser(r)
	response := map[string]any{
		"permissions": levelsToNames[user.Permissions],
		"mxid":        user.MXID.String(),
	}

	ul := user.GetDefaultLogin()
	if ul.ID != "" { // if logged in
		linClient := connector.NewLinkedInClient(r.Context(), m.Connector.(*connector.LinkedInConnector), ul)

		currentUser, err := linClient.GetCurrentUser()
		if err == nil {
			response["linkedin"] = currentUser
		}
	}

	exhttp.WriteJSONResponse(w, http.StatusOK, response)
}

func legacyProvLogin(w http.ResponseWriter, r *http.Request) {
	user := m.Matrix.Provisioning.GetUser(r)
	ctx := r.Context()
	var body map[string]map[string]string
	err := json.NewDecoder(r.Body).Decode(&body)
	if err != nil {
		exhttp.WriteJSONResponse(w, http.StatusBadRequest, mautrix.MBadJSON.WithMessage(err.Error()))
		return
	}
	cookieString := body["all_headers"]["Cookie"]

	lp, err := m.Connector.CreateLogin(ctx, user, "cookies")
	if err != nil {
		zerolog.Ctx(ctx).Err(err).Msg("Failed to create login")
		exhttp.WriteJSONResponse(w, http.StatusInternalServerError, mautrix.MUnknown.WithMessage("Internal error creating login"))
	} else if firstStep, err := lp.Start(ctx); err != nil {
		zerolog.Ctx(ctx).Err(err).Msg("Failed to start login")
		exhttp.WriteJSONResponse(w, http.StatusInternalServerError, mautrix.MUnknown.WithMessage("Internal error starting login"))
	} else if firstStep.StepID != connector.LoginStepIDCookies {
		exhttp.WriteJSONResponse(w, http.StatusInternalServerError, mautrix.MUnknown.WithMessage("Unexpected login step"))
	} else if !connector.ValidCookieRegex.MatchString(cookieString) {
		exhttp.WriteJSONResponse(w, http.StatusOK, nil)
	} else if finalStep, err := lp.(bridgev2.LoginProcessCookies).SubmitCookies(ctx, map[string]string{
		"cookie": cookieString,
	}); err != nil {
		zerolog.Ctx(ctx).Err(err).Msg("Failed to log in")
		var respErr bridgev2.RespError
		if errors.As(err, &respErr) {
			exhttp.WriteJSONResponse(w, respErr.StatusCode, &respErr)
		} else {
			exhttp.WriteJSONResponse(w, http.StatusInternalServerError, mautrix.MUnknown.WithMessage("Internal error logging in"))
		}
	} else if finalStep.StepID != connector.LoginStepIDComplete {
		exhttp.WriteJSONResponse(w, http.StatusInternalServerError, mautrix.MUnknown.WithMessage("Unexpected login step"))
	} else {
		exhttp.WriteJSONResponse(w, http.StatusOK, map[string]any{})
		go handleLoginComplete(context.WithoutCancel(ctx), user, finalStep.CompleteParams.UserLogin)
	}
}

func handleLoginComplete(ctx context.Context, user *bridgev2.User, newLogin *bridgev2.UserLogin) {
	allLogins := user.GetUserLogins()
	for _, login := range allLogins {
		if login.ID != newLogin.ID {
			login.Delete(ctx, status.BridgeState{StateEvent: status.StateLoggedOut, Reason: "LOGIN_OVERRIDDEN"}, bridgev2.DeleteOpts{})
		}
	}
}

func legacyProvLogout(w http.ResponseWriter, r *http.Request) {
	user := m.Matrix.Provisioning.GetUser(r)
	logins := user.GetUserLogins()
	for _, login := range logins {
		// Intentionally don't delete the user login, only disconnect the client
		login.Client.(*connector.LinkedInClient).LogoutRemote(r.Context())
	}
	exhttp.WriteJSONResponse(w, http.StatusOK, map[string]any{
		"success": true,
		"status":  "logged_out",
	})
}
