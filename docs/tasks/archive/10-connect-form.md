# Task 10: Connect/Outreach Form with Moderation

## Objective

Allow visitors to send a message to a member or business through the
site. All messages are moderated by admins before being delivered.
Protect against spam, abuse, and data exfiltration.

## User Flow

```
Visitor sees profile → clicks "Connect" → fills form → submits
   → message stored as "pending"
   → admin notified
   → admin reviews: approve / reject / spam
   → if approved: member notified (email or in-app)
```

## Form Fields

Based on the reference screenshot:

- **Your name** (required, max 100 chars)
- **Your email address** (required, valid email format)
- **Message** (required, max 2000 chars)
- **Honeypot field** (hidden, must be empty)
- **Connect button** (submit)

## Database Model: ConnectMessage

Add to `api/models.py`:

```python
class ConnectMessage(Base):
    __tablename__ = "connect_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_profile_id: Mapped[int] = mapped_column(Integer, index=True)
    sender_name: Mapped[str] = mapped_column(String)
    sender_email: Mapped[str] = mapped_column(String)
    message_body: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    honeypot_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

## API Endpoints

### Public: Submit a connect request

```
POST /api/v1/public/connect
```

Request body:
```json
{
  "recipient_id": 372,
  "sender_name": "Jane Doe",
  "sender_email": "jane@example.com",
  "message": "I'd like to learn about your workshops.",
  "website": ""  // honeypot field — must be empty
}
```

Response: `201 Created` with `{"status": "pending", "message": "Your
message has been submitted for review."}`

### Admin: List pending messages

```
GET /api/v1/admin/connect?status=pending
```

### Admin: Review a message

```
PUT /api/v1/admin/connect/:id
```

Body: `{"status": "approved"}` or `{"status": "rejected"}` or
`{"status": "spam"}`

## Security & Anti-Abuse Measures

### 1. Honeypot field

The form includes a hidden field named `website` (or similar innocuous
name). CSS hides it from real users. Bots fill it in. If the field has
any value, the submission is auto-flagged as spam.

```html
<div style="position: absolute; left: -9999px;" aria-hidden="true">
  <label for="website">Website</label>
  <input type="text" name="website" id="website" tabindex="-1" autocomplete="off">
</div>
```

### 2. Rate limiting

Per-IP rate limit: max 5 submissions per hour. Implement with a simple
in-memory counter or a lightweight middleware. Returns `429 Too Many
Requests` if exceeded.

### 3. Content filtering

Before storing, check the message for:
- Excessive URLs (> 2 links → flag for review)
- Known spam patterns (regex for common spam phrases)
- Extremely short messages (< 10 chars → reject)
- Extremely long messages (> 2000 chars → truncate)

### 4. Email validation

Basic format check on `sender_email`. Do not send any emails to the
sender's address (prevents being used as an email relay).

### 5. No PII exposure

The form never reveals the recipient's email address. Messages are
stored in the DB and the admin decides whether to forward them. The
recipient's contact info is never sent to the visitor.

### 6. CSRF protection

If the form is rendered by Astro (static site), CSRF tokens may not be
practical. Alternative protections:
- Require a `Referer` header matching the site origin
- Rate limiting (above)
- The honeypot field catches most automated submissions

### 7. Input sanitization

All user input is stored as plain text. When rendering:
- HTML-escape all output
- Never render user-submitted HTML
- Strip any `<script>`, `<iframe>`, etc.

## Astro Integration

Add a connect form component to the business detail page (Task 9) and
optionally to member cards:

```html
<form action="${apiBaseUrl}/api/v1/public/connect" method="POST">
  <input type="hidden" name="recipient_id" value="${profile.id}">
  <!-- honeypot -->
  <div style="position:absolute;left:-9999px" aria-hidden="true">
    <input name="website" tabindex="-1" autocomplete="off">
  </div>
  <label>Your name<input name="sender_name" required maxlength="100"></label>
  <label>Your email<input name="sender_email" type="email" required></label>
  <label>Message<textarea name="message" required maxlength="2000"></textarea></label>
  <button type="submit">Connect</button>
</form>
```

Style the form to match the screenshot: clean, minimal, yellow
"Connect" button.

## Admin Notification

When a new message is submitted:
- Log it to stdout (visible in server logs)
- (Future) Send an email notification to a configured admin address
- (Future) Webhook to Slack or similar

## Deliverables

- [ ] `ConnectMessage` model added to `api/models.py`
- [ ] `POST /api/v1/public/connect` endpoint with validation
- [ ] Honeypot field check
- [ ] Rate limiting (per-IP, 5/hour)
- [ ] Content filtering (excessive URLs, min length)
- [ ] `GET /api/v1/admin/connect` — list messages by status
- [ ] `PUT /api/v1/admin/connect/:id` — approve/reject/spam
- [ ] Connect form on business detail page (Astro)
- [ ] Form styled to match the screenshot reference
- [ ] All user input sanitized and HTML-escaped on output
