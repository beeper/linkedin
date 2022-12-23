# v0.5.4

**Migrated away from Poetry**. The dependency management was getting very
annoying, and it was quite different from the dependency management of all of
the other mautrix Python bridges, so I switched to use `setup.py` and
`requirements.txt`.

**Features**

* Added `login-manual` option to log in to LinkedIn using a manual login flow.

  You can now pull the cookies manually from within an incognito browser after
  logging in instead of using the (very unreliable) old login method.

* Added personal filtering space support.

**Internal**

* Updated to `mautrix>=0.18.7,<0.19`.
* Add support for SQLite.

# v0.5.3

**Migrated to GitHub**. You should change all of your Docker images to point to
ghcr rather than registry.gitlab.com. For example:
```
registry.gitlab.com/beeper/linkedin:latest
```
should become
```
ghcr.io/beeper/linkedin:latest
```

You'll also need to change your git commit URLs.

**Features**

* Implemented typing notifications
* Implemented read receipts

**Other changes:**

* Switched to GitHub Actions for CI/CD
* Added pre-commit config to help prevent bad pushes
* Upgraded `mautrix` to `^0.17.6`
* Upgraded `linkedin-messaging` to `^0.5.2`
* Converted to use `isort` instead of `flake8-import-order`

# v0.5.2

* Upgraded mautrix to `^0.14.0`
* Major improvements across the board for message send status reporting via
  native Matrix notices and via message send checkpoints.

# v0.5.1

* Add support for shared feed posts.

# v0.5.0

* Upgraded mautrix to `^0.10.3`
* Upgraded asyncpg to `>=0.23.0`
* Made the ruamel.yaml requirement less strict (`^0.17.0`)
* Fixed a few errors with bridge state sending
* Implemented support for the manhole
* Add caching for user profile to improve speed of whoami calls
* Add flags to track whether name, avatar, and topic are set on the portal
* Fixed bug with initial setting of room avatars on DMs

# v0.4.1

* Upgraded mautrix to 0.10.1+
* Implemented new bridge state pushing
* Infra: added `latest` tag to the Docker image when running for a tag.
  Hopefully this helps speed up incremental builds in the future.

# v0.4.0

* Upgraded to support only Python 3.9+.
* Added Prometheus metrics support.
* Infrastructure: improved Docker container dependency management by moving more
  of the packages to use the Alpine-provided versions.
* On DM rooms, set the topic to the other users' occupation and include a link
  to to their LinkedIn profile. This option can be turned off by setting
  `bridge.set_topic_on_dms` to `false`.
* Added support for custom names on group chats and handling name change events.
* Added handling for emote formatting on plain-text messages.
* When a chat is read in Matrix, it is now marked as read in LinkedIn.
* Improved handling of promotional InMail messages.
* Bug fix: respect `bridge.initial_chat_sync` and `backfill` parameters.
* Send more bridging errors to the room.

# v0.3.0

* Updated `linkedin-messaging` to
  [v0.3.0](https://github.com/sumnerevans/linkedin-messaging-api/releases/tag/v0.3.0).
* Handle redactions to/from LinkedIn. (#18, #32, #37, #38)
* Handle real-time reactions to/from LinkedIn. (#19, #31, #32)
* Enabled sending app-service bot delivery receipts to the chat.
* Fixed `reaction` database table primary key to support multiple reactions per
  user, per message.

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
