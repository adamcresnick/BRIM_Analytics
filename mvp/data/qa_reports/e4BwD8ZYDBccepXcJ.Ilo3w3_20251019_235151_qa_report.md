# Patient QA Report: e4BwD8ZYDBccepXcJ.Ilo3w3

**Generated**: 2025-10-19 23:51:51
**Agent 1 (Claude)**: Orchestration and QA
**Agent 2 (MedGemma)**: Extraction

---

## Executive Summary

- **Total imaging events analyzed**: 51
- **Inconsistencies detected**: 8
- **Requires human review**: Yes ⚠️

### Inconsistency Breakdown

- **duplicate**: 6
- **temporal**: 1
- **wrong_type**: 1

---

## Detected Inconsistencies

### 1. DUPLICATE - high

**Description**: Duplicate events on 2018-08-03 00:00:00: 2 events

**Affected Events**: img_erNFnh2TkBgIXlRW7wzruHE1QFHAqtgsQTIDnGsl7l-A3, img_erNFnh2TkBgIXlRW7wzruHAUPWUNW-RW9M7omUgUyBQE3

**Events on same date**:
- img_erNFnh2TkBgIXlRW7wzruHE1QFHAqtgsQTIDnGsl7l-A3: Increased (conf: 0.80)
- img_erNFnh2TkBgIXlRW7wzruHAUPWUNW-RW9M7omUgUyBQE3: Increased (conf: 0.95)

**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence

---

### 2. DUPLICATE - high

**Description**: Duplicate events on 2018-09-07 00:00:00: 2 events

**Affected Events**: img_eTFONpFWsISlRf.a8Vam6HRnTQry4-qvSdTGnVh-uPxU3, img_eTFONpFWsISlRf.a8Vam6HTtA9bs691lZVAW553jRJuU3

**Events on same date**:
- img_eTFONpFWsISlRf.a8Vam6HRnTQry4-qvSdTGnVh-uPxU3: Increased (conf: 0.85)
- img_eTFONpFWsISlRf.a8Vam6HTtA9bs691lZVAW553jRJuU3: Increased (conf: 0.85)

**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence

---

### 3. DUPLICATE - high

**Description**: Duplicate events on 2019-01-25 00:00:00: 2 events

**Affected Events**: img_eC-i1ZrMac9dAlsIByg0XlGHHNrAcYkiGNo7.COnQboU3, img_esNMlSYzVdZw4oIHSCc6Wkt8caciflg.BSirMvP90doc3

**Events on same date**:
- img_eC-i1ZrMac9dAlsIByg0XlGHHNrAcYkiGNo7.COnQboU3: Stable (conf: 0.95)
- img_esNMlSYzVdZw4oIHSCc6Wkt8caciflg.BSirMvP90doc3: Stable (conf: 0.95)

**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence

---

### 4. DUPLICATE - high

**Description**: Duplicate events on 2021-03-15 00:00:00: 2 events

**Affected Events**: img_eIfXpVFtfWhx0EwCdV-KQS7u6TUqasW6oYfPYIVuMV9s3, img_ePKznVk59GM2u7XDqG6zFzE-5XrSDwUAlUYBMWz6FfdE3

**Events on same date**:
- img_eIfXpVFtfWhx0EwCdV-KQS7u6TUqasW6oYfPYIVuMV9s3: Stable (conf: 0.85)
- img_ePKznVk59GM2u7XDqG6zFzE-5XrSDwUAlUYBMWz6FfdE3: Stable (conf: 0.95)

**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence

---

### 5. DUPLICATE - high

**Description**: Duplicate events on 2024-04-30 00:00:00: 2 events

**Affected Events**: img_eXWDGYhrdqFL1ZKNXRvgTqOqy33rNyRu2Utf-BIEMIls3, img_eXWDGYhrdqFL1ZKNXRvgTqOneClv5-lAzEyazzHrCKjI3

**Events on same date**:
- img_eXWDGYhrdqFL1ZKNXRvgTqOqy33rNyRu2Utf-BIEMIls3: Stable (conf: 0.95)
- img_eXWDGYhrdqFL1ZKNXRvgTqOneClv5-lAzEyazzHrCKjI3: Stable (conf: 0.95)

**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence

---

### 6. DUPLICATE - high

**Description**: Duplicate events on 2024-09-27 00:00:00: 2 events

**Affected Events**: img_eRByHC5fWfjRze8IdU7LmUrMmaJQG8KD95ixOZZdy55U3, img_eTBviDBZPdSjeXACF.vmwPOVxsoWtll.80aOCKZG.cCc3

**Events on same date**:
- img_eRByHC5fWfjRze8IdU7LmUrMmaJQG8KD95ixOZZdy55U3: Gross Total Resection (conf: 0.95)
- img_eTBviDBZPdSjeXACF.vmwPOVxsoWtll.80aOCKZG.cCc3: NED (conf: 0.85)

**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence

---

### 7. TEMPORAL - high

**Description**: Status changed Increased→Decreased in 2 days

**Affected Events**: img_egCavClt7q8KwyBCgPS0JXrAMVCHX-E0Q1D-Od9nchS03, img_eEe13sHGFL.xUsHCNkt59VBryiQKdqIv6WLgdMCHLZ3U3

**Timeline**:
- **Prior**: 2018-05-27 00:00:00 - Increased (conf: 0.80)
- **Current**: 2018-05-29 00:00:00 - Decreased (conf: 0.85)
- **Time gap**: 2 days

**Agent 1 Assessment**: Rapid status change without documented treatment intervention suggests:
1. Possible duplicate scan
2. Possible misclassification by Agent 2
3. Requires Agent 2 re-review with additional context

**Recommended Action**: Query Agent 2 for explanation and multi-source validation

---

### 8. WRONG_TYPE - high

**Description**: 'Gross Total Resection' is EOR, not tumor_status

**Affected Events**: img_eRByHC5fWfjRze8IdU7LmUrMmaJQG8KD95ixOZZdy55U3

**Misclassified Value**: `Gross Total Resection`

**Agent 1 Assessment**: This value belongs to `extent_of_resection`, not `tumor_status`

**Agent 1 Resolution**: Re-extract using correct variable type

---

## Recommendations for Human Review

⚠️ **8 high-priority issues require review**

1. **duplicate**: Duplicate events on 2018-08-03 00:00:00: 2 events
   - Events: img_erNFnh2TkBgIXlRW7wzruHE1QFHAqtgsQTIDnGsl7l-A3, img_erNFnh2TkBgIXlRW7wzruHAUPWUNW-RW9M7omUgUyBQE3

1. **duplicate**: Duplicate events on 2018-09-07 00:00:00: 2 events
   - Events: img_eTFONpFWsISlRf.a8Vam6HRnTQry4-qvSdTGnVh-uPxU3, img_eTFONpFWsISlRf.a8Vam6HTtA9bs691lZVAW553jRJuU3

1. **duplicate**: Duplicate events on 2019-01-25 00:00:00: 2 events
   - Events: img_eC-i1ZrMac9dAlsIByg0XlGHHNrAcYkiGNo7.COnQboU3, img_esNMlSYzVdZw4oIHSCc6Wkt8caciflg.BSirMvP90doc3

1. **duplicate**: Duplicate events on 2021-03-15 00:00:00: 2 events
   - Events: img_eIfXpVFtfWhx0EwCdV-KQS7u6TUqasW6oYfPYIVuMV9s3, img_ePKznVk59GM2u7XDqG6zFzE-5XrSDwUAlUYBMWz6FfdE3

1. **duplicate**: Duplicate events on 2024-04-30 00:00:00: 2 events
   - Events: img_eXWDGYhrdqFL1ZKNXRvgTqOqy33rNyRu2Utf-BIEMIls3, img_eXWDGYhrdqFL1ZKNXRvgTqOneClv5-lAzEyazzHrCKjI3

1. **duplicate**: Duplicate events on 2024-09-27 00:00:00: 2 events
   - Events: img_eRByHC5fWfjRze8IdU7LmUrMmaJQG8KD95ixOZZdy55U3, img_eTBviDBZPdSjeXACF.vmwPOVxsoWtll.80aOCKZG.cCc3

1. **temporal**: Status changed Increased→Decreased in 2 days
   - Events: img_egCavClt7q8KwyBCgPS0JXrAMVCHX-E0Q1D-Od9nchS03, img_eEe13sHGFL.xUsHCNkt59VBryiQKdqIv6WLgdMCHLZ3U3

1. **wrong_type**: 'Gross Total Resection' is EOR, not tumor_status
   - Events: img_eRByHC5fWfjRze8IdU7LmUrMmaJQG8KD95ixOZZdy55U3

## Next Steps

1. **Agent 1**: Query Agent 2 for explanations of temporal inconsistencies
2. **Agent 1**: Gather additional sources (imaging PDFs, progress notes) for multi-source validation
3. **Agent 1**: Re-extract with correct variable types where needed
4. **Human**: Review escalated issues and provide final adjudication
