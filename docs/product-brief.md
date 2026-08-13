# Product Brief — Windows Patch Dashboard

## Problem
Microsoft publishes Windows security-update information across multiple official surfaces. The data is public but operationally inconvenient to consume: users must locate the correct KB per supported operating system, read long support articles, identify key changes, separate fixed issues from known issues, and revisit the information when OOB updates appear.

## Product goal
Provide a small public web application that organizes official Microsoft update information into a concise monthly table that can be understood quickly and exported as a clean image.

## Primary audience
Infrastructure, security, DevOps, sysadmin, patch-management, vulnerability-management, and IT operations professionals.

## V1 scope
Cover only:
- Windows Server 2012 (ESU)
- Windows Server 2012 R2 (ESU)
- Windows Server 2016
- Windows Server 2019
- Windows Server 2022
- Windows Server 2025
- Windows 11 supported branches relevant to the selected month

The canonical report columns are:
1. KB
2. OS
3. Vulnerabilidades / Cambios Clave
4. Issues Resueltos
5. Problemas Conocidos

The UI may add metadata/status indicators outside those five canonical report columns.

## Special rules
- Windows Server 2012/2012 R2: include only ESU updates; if expected but not published, still render a row with `NO PUBLICADO`.
- Do not show CVE counts by severity.
- Summaries should be concise and operational, not marketing copy.
- Known Issues must distinguish `none`, `open`, and unresolved/unknown data.
- OOB updates must be representable without overwriting history.

## Non-goals for V1
- Full vulnerability management platform.
- Device inventory.
- Patch compliance.
- Authentication/accounts.
- User-specific environments.
- Database-backed API.
- Azure hosting.
- AI chatbot.
- Complex analytics/charts.
