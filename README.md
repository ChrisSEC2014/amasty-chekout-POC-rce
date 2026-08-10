# CVE-2026-53787 - Amasty Order Attributes Unauthenticated File Upload

## Description

CVE-2026-53787 is a critical unauthenticated arbitrary file upload vulnerability in the Amasty Order Attributes extension for Magento 2 versions prior to 4.0.0 . The vulnerability allows attackers to upload files of any type or name to the store's media directory without requiring authentication, session validation, or cart context .

## Impact

The attack requires no credentials and can be executed over the network . The vulnerability has a CVSS score of 9.8 (Critical) . A successful exploit can lead to:

- Remote Code Execution (RCE) if PHP execution is permitted in the media directory, giving attackers full server control 
- Malware hosting using the trusted domain 
- Stored Cross-Site Scripting (XSS) via HTML or SVG uploads 
- Path traversal attacks to write files outside the intended upload directory 

## Affected Endpoints

The vulnerability targets the following REST endpoints :

```
POST /rest/V1/amasty_orderattr/uploadFile
POST /rest/all/V1/amasty_orderattr/uploadFile
POST /rest/default/V1/amasty_orderattr/uploadFile
```

## Exploitation Activity

Mass exploitation began hours after the patch was released on June 12, 2026 . By June 15, over 12,000 exploitation attempts were detected against 25% of all Magento stores .

## Remediation

- Upgrade Amasty Order Attributes to version 4.0.0 or later 
- Configure the web server to disable PHP execution in the media directory 
- Implement strict file upload validation and extension allow-lists 
