# v0.2.1

* Added `prometheus-client` as an optional dependency.
* Added a couple basic metrics to the bridge.

# v0.2.0

* Updated `linkedin-messaging` to
  [v0.2.1](https://github.com/sumnerevans/linkedin-messaging-api/releases/tag/v0.2.1).
* Pinned `python-olm` at 3.2.1.
* Implemented logout. (#56)
* Migrated to GitLab from GitHub. Be sure to update your remotes!
* Added automated Docker container build. See the image registry here:
  https://gitlab.com/beeper/linkedin-matrix/container_registry.
* Changed `real_user_content_key` to `com.sumnerevans.linkedin.puppet`.
* Added provisioning API for managing the bridge over HTTP(S).
* Fixed some instances of text that was copied from other bridges to correctly
  reference LinkedIn.

# v0.1.1

* Fixed the `bridge.resend_bridge_info` option.
* Addressed many linter errors.
* Fixed handling of InMail messages.

# v0.1.0

Initial Alpha release. **Note that LinkedIn may flag the traffic from your
account as suspicious due to using this bridge. We are not responsible if your
account gets banned or locked.** In the future, I hope to implement infinite
incremental backfill using
[MSC2716](https://github.com/matrix-org/matrix-doc/pull/2716) which should allow
for rate-limiting and during backfill so it doesn't look like as much like a
scraper bot.

The current feature set includes:

* Backfill of messages from LinkedIn to Matrix
* Message puppeting from LinkedIn -> Matrix in real-time
  * Supported message types: text, files, images, GIFs
  * Formatting supported: mentions
* Message sending from Matrix to LinkedIn
  * Supported message types: text, files, images, videos, GIFs
  * Formatting supported: mentions, emotes
* User metadata puppeting: profile picture, first/last name
