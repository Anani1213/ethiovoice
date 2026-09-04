# EthioVoice AI 🎙️

**Voice-first accessibility for Ethio Telecom & Telebirr services**

EthioVoice AI is a proof-of-concept assistant built for the Ethio Telecom competition. It lets users interact with core telecom services — balance checks, package purchases, and Telebirr transfers — using natural Amharic voice or text commands, lowering the barrier for users with low literacy or limited familiarity with USSD codes and app menus.

> ⚠️ **Disclaimer:** This is an independent competition/demo project. It is **not affiliated with, endorsed by, or connected to Ethio Telecom or Telebirr**. All transactions are simulated locally — no real money, airtime, or data is transferred.

## Problem Statement

Many Ethio Telecom customers, especially in rural areas or with limited literacy, find USSD codes (like `*804#`) and app navigation difficult. EthioVoice AI explores a voice-first, Amharic-native interface as a more accessible alternative.

## Features

- 🗣️ **Amharic command input** — type (or eventually speak) natural Amharic phrases instead of memorizing USSD codes
- 🧠 **Keyword-based intent recognition** — maps free-form Amharic text to the correct service
- 📊 **Balance check simulation** — mirrors the `*804#` airtime/data/minutes balance flow
- 📦 **Package purchase simulation** — browse and "buy" data or voice bundles, with balance deduction
- 💸 **Telebirr transfer simulation** — simulate sending money to a phone number with transaction ID generation
- 🕒 **Activity history** — recent simulated actions shown in-session
- 📁 **Config-driven responses** — all Amharic prompts, intents, and templates live in `prompts.json` for easy editing without touching code

## Tech Stack

- **Python 3**
- **Streamlit** — UI framework
- **JSON** — configuration for intents, packages, and response templates

## Project Structure
