package main

import (
	up "go.mau.fi/util/configupgrade"
)

func migrateLegacyConfig(helper up.Helper) {
	helper.Set(up.Str, "mautrix.bridge.e2ee", "encryption", "pickle_key")
}
