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
