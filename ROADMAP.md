# Features & roadmap

* Matrix → LinkedIn
  * [x] Message content
    * [x] Text
    * [x] Media
      * [x] Files
      * [x] Images
      * [x] Videos
      * [x] GIFs
      * [x] Voice Messages
      * [ ] ~~Stickers~~ (unsupported)
    * [ ] ~~Formatting~~ (LinkedIn does not support rich formatting)
    * [x] Replies
    * [ ] Mentions
    * [ ] Emotes
  * [x] Message redactions
  * [x] Message reactions
  * [ ] Presence
  * [ ] Typing notifications
  * [ ] Read receipts
  * [ ] Power level
  * [ ] Membership actions
    * [ ] Invite
    * [ ] Kick
    * [ ] Leave
  * [x] Room metadata changes
    * [x] Name
    * [x] Avatar
    * [ ] Per-room user nick
* LinkedIn → Matrix
  * [x] Message content
    * [x] Text
    * [x] Media
      * [x] Files
      * [x] Images
      * [x] GIFs
      * [x] Voice Messages
    * [ ] Mentions
  * [ ] Message delete
  * [x] Message reactions
  * [x] Message history
  * [x] Real-time messages
  * [ ] ~~Presence~~ (impossible for now, see https://github.com/mautrix/go/issues/295)
  * [ ] Typing notifications
  * [ ] Read receipts
  * [ ] Admin status
  * [ ] Membership actions
    * [ ] Add member
    * [ ] Remove member
    * [ ] Leave
  * [ ] Chat metadata changes
    * [ ] Title
    * [ ] Avatar
  * [ ] Initial chat metadata
  * [ ] User metadata
    * [ ] Name
    * [ ] Avatar
* Misc
  * [ ] Multi-user support
  * [ ] Shared group chat portals
  * [x] Automatic portal creation
    * [x] At startup
    * [x] When added to chat
    * [ ] When receiving message (not supported)
  * [ ] Private chat creation by inviting Matrix puppet of LinkedIn user to new room
  * [ ] Option to use own Matrix account for messages sent from other LinkedIn clients (relay mode)
  * [ ] Split portal support
