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
    removeLogo: "Удалить логотип",
    logoCurrent: "Текущий логотип",
    noLogo: "Логотип не загружен",
    systemSettings: "Системные настройки",
    systemSettingsHint: "JSON-конфигурация (ключ-значение)",
    helpText: "Текст справки",
    helpTextHint: "Markdown-разметка для страницы /help",
    save: "Сохранить",
    saving: "Сохранение...",
    saved: "Настройки сохранены",
    saveError: "Ошибка сохранения",
    logoUploaded: "Логотип загружен",
    logoRemoved: "Логотип удалён",
    logoUploadError: "Ошибка загрузки логотипа",
    logoRemoveError: "Ошибка удаления логотипа",

    // Help page
    helpTitle: "Справка / Инструкция",
    helpSubtitle: "Руководство по использованию Inviter Pro",
    helpContent: `
# Inviter Pro — Руководство пользователя

## 1. Обзор

Inviter Pro — это самохостируемый инструмент для автоматизации приглашений в Telegram-группы.

## 2. Аккаунты

Добавьте Telegram-аккаунты, загрузите \`.session\` файлы и выполните проверку.

## 3. Прокси

Настройте прокси-серверы для распределения нагрузки между аккаунтами.

## 4. Парсер

Спарсите участников из Telegram-групп для последующих приглашений.

## 5. Кампании

Создавайте кампании для массового приглашения. Указывайте лимиты и расписание.

## 6. Настройки

- **Язык** — переключает интерфейс между RU и EN
- **Логотип** — загружает собственное изображение
- **Текст справки** — markdown-контент для страницы помощи
- **Системные настройки** — расширенная JSON-конфигурация

## 7. Безопасность

- Используйте отдельный прокси для каждого аккаунта
- Не превышайте дневные лимиты Telegram
- Регулярно проверяйте статус аккаунтов
    `.trim(),

    // Dashboard
    welcome: "Добро пожаловать в Inviter Pro",

    // Common
    loading: "Загрузка...",
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
    languageRu: "Russian",
    languageEn: "English",
    siteName: "Site name",
    siteNamePlaceholder: "Enter site name",
    uploadLogo: "Upload logo",
    removeLogo: "Remove logo",
    logoCurrent: "Current logo",
    noLogo: "No logo uploaded",
    systemSettings: "System settings",
    systemSettingsHint: "JSON configuration (key-value)",
    helpText: "Help text",
    helpTextHint: "Markdown content for the /help page",
    save: "Save",
    saving: "Saving...",
    saved: "Settings saved",
    saveError: "Save error",
    logoUploaded: "Logo uploaded",
    logoRemoved: "Logo removed",
    logoUploadError: "Logo upload error",
    logoRemoveError: "Logo removal error",

    // Help page
    helpTitle: "Help / Instructions",
    helpSubtitle: "Guide for using Inviter Pro",
    helpContent: `
# Inviter Pro — User Guide

## 1. Overview

Inviter Pro is a self-hosted tool for automating Telegram group invitations.

## 2. Accounts

Add Telegram accounts, upload \`.session\` files and run the check.

## 3. Proxies

Configure proxy servers to distribute load across accounts.

## 4. Parser

Parse members from Telegram groups for subsequent invitations.

## 5. Campaigns

Create campaigns for mass invitations. Set limits and schedules.

## 6. Settings

- **Language** — switch the interface between RU and EN
- **Logo** — upload your own image
- **Help text** — markdown content for the help page
- **System settings** — advanced JSON configuration

## 7. Security

- Use a proxy for each account
- Do not exceed daily Telegram limits
- Regularly check account status
    `.trim(),

    // Dashboard
    welcome: "Welcome to Inviter Pro",

    // Common
    loading: "Loading...",
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
