# FindYourAd Telegram Bot

FindYourAd is a Telegram bot for connecting advertisers and channel owners.  
It acts as an advertising marketplace, allowing users to post ads and channels, browse offers, and manage their listings.

## Features

- **Role selection:** Users choose to be an advertiser or a channel seller.
- **Advertisers:**  
  - Add advertising requests with description, audience, tags, and price.
  - Browse available channels.
  - View and delete their own requests.
- **Channel Sellers:**  
  - Add channels with link, name, price per post, and tags.
  - Browse advertising requests.
  - View and delete their own channels.
- **Inline buttons and commands:**  
  - Easy navigation and management via Telegram interface.
- **SQLite database:**  
  - Stores users, requests, and channels securely.

## Usage

- Start the bot and select your role.
- Use commands like `/add_request`, `/add_channel`, `/view_requests`, `/view_channels`, `/my_requests`, `/my_channels`.
- Manage your ads and channels directly in Telegram.

## Technologies

- Python
- python-telegram-bot
- SQLite

## Getting Started

1. Clone the repository.
2. Install dependencies.
3. Run bot.py with your Telegram bot token.

---

**FindYourAd** helps advertisers and channel owners find each other and make deals easily in Telegram!
