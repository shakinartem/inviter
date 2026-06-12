export type Locale = "ru" | "en";

const translations: Record<Locale, Record<string, string>> = {
  ru: {
    // Sidebar
    dashboard: "Панель",
    accounts: "Аккаунты",
    proxies: "Прокси",
    parser: "Парсер",
    campaigns: "Кампании",
    settings: "Настройки",
    help: "Справка",
    logout: "Выйти",
    logoPlaceholder: "Inviter Pro",

    // Settings page
    settingsTitle: "Настройки",
    settingsSubtitle: "Управление языком, логотипом и системными настройками",
    language: "Язык интерфейса",
    languageRu: "Русский",
    languageEn: "English",
    siteName: "Название сайта",
    siteNamePlaceholder: "Введите название",
    uploadLogo: "Загрузить логотип",
    logoCurrent: "Текущий логотип",
    noLogo: "Логотип не загружен",
    systemSettings: "Системные настройки",
    systemSettingsHint: "JSON-конфигурация (ключ-значение)",
    save: "Сохранить",
    saving: "Сохранение…",
    saved: "Настройки сохранены",
    saveError: "Ошибка сохранения",
    logoUploaded: "Логотип загружен",
    logoUploadError: "Ошибка загрузки логотипа",

    // Help page
    helpTitle: "Справка / Инструкция",
    helpSubtitle: "Руководство по использованию Inviter Pro",
    helpContent: `
# Inviter Pro — Руководство пользователя

## 1. Обзор

Inviter Pro — это самохостируемый инструмент для автоматизации приглашений в Telegram-группы.

## 2. Аккаунты

Добавьте Telegram-аккаунты, загрузите .session файлы и выполните проверку.

## 3. Прокси

Настройте прокси-серверы для распределения нагрузки между аккаунтами.

## 4. Парсер

Спарсите участников из Telegram-групп для последующего приглашения.

## 5. Кампании

Создайте кампании для массового приглашения. Установите лимиты и расписание.

## 6. Настройки

- **Язык** — переключите интерфейс на RU или EN
- **Логотип** — загрузите собственное изображение
- **Системные настройки** — расширенная JSON-конфигурация

## 7. Безопасность

- Используйте прокси для каждого аккаунта
- Не превышайте дневные лимиты Telegram (рекомендуется до 30 инвайтов/день)
- Регулярно проверяйте статус аккаунтов
    `.trim(),

    // Dashboard
    welcome: "Добро пожаловать в Inviter Pro",

    // Common
    loading: "Загрузка…",
    error: "Ошибка",
    retry: "Повторить",
  },

  en: {
    // Sidebar
    dashboard: "Dashboard",
    accounts: "Accounts",
    proxies: "Proxies",
    parser: "Parser",
    campaigns: "Campaigns",
    settings: "Settings",
    help: "Help",
    logout: "Logout",
    logoPlaceholder: "Inviter Pro",

    // Settings page
    settingsTitle: "Settings",
    settingsSubtitle: "Manage language, logo and system settings",
    language: "Interface language",
    languageRu: "Русский",
    languageEn: "English",
    siteName: "Site name",
    siteNamePlaceholder: "Enter site name",
    uploadLogo: "Upload logo",
    logoCurrent: "Current logo",
    noLogo: "No logo uploaded",
    systemSettings: "System settings",
    systemSettingsHint: "JSON configuration (key-value)",
    save: "Save",
    saving: "Saving…",
    saved: "Settings saved",
    saveError: "Save error",
    logoUploaded: "Logo uploaded",
    logoUploadError: "Logo upload error",

    // Help page
    helpTitle: "Help / Instructions",
    helpSubtitle: "Guide for using Inviter Pro",
    helpContent: `
# Inviter Pro — User Guide

## 1. Overview

Inviter Pro is a self-hosted tool for automating Telegram group invitations.

## 2. Accounts

Add Telegram accounts, upload .session files and run the check.

## 3. Proxies

Configure proxy servers to distribute load across accounts.

## 4. Parser

Parse members from Telegram groups for subsequent invitations.

## 5. Campaigns

Create campaigns for mass invitations. Set limits and schedules.

## 6. Settings

- **Language** — switch the interface between RU and EN
- **Logo** — upload your own image
- **System settings** — advanced JSON configuration

## 7. Security

- Use a proxy for each account
- Do not exceed daily Telegram limits (recommended up to 30 invites/day)
- Regularly check account status
    `.trim(),

    // Dashboard
    welcome: "Welcome to Inviter Pro",

    // Common
    loading: "Loading…",
    error: "Error",
    retry: "Retry",
  },
};

let currentLocale: Locale =
  (localStorage.getItem("locale") as Locale) || "ru";

export function setLocale(locale: Locale) {
  currentLocale = locale;
  localStorage.setItem("locale", locale);
}

export function getLocale(): Locale {
  return currentLocale;
}

export function t(key: string): string {
  return translations[currentLocale]?.[key] ?? key;
}

export default translations;