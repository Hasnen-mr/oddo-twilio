/** @odoo-module **/

/**
 * Update a UI-only field on a settings record without marking the form dirty.
 *
 * res.config.settings rows are often "new" records whose entire payload lives in
 * `_changes` while `dirty` is still false. Calling `record.update()` would set
 * `dirty = true` and incorrectly trigger "Unsaved changes".
 */
export function setUiField(record, fieldName, value) {
    if (!record || record.data[fieldName] === value) {
        return;
    }
    const wasDirty = record.dirty;
    if (record._changes && Object.prototype.hasOwnProperty.call(record._changes, fieldName)) {
        record._changes[fieldName] = value;
    } else if (record._values) {
        record._values[fieldName] = value;
    } else {
        return;
    }
    // Keep both maps in sync when the field exists in both (rare).
    if (record._values && fieldName in record._values) {
        record._values[fieldName] = value;
    }
    if (record._changes && fieldName in record._changes) {
        record._changes[fieldName] = value;
    }
    record.data = { ...record._values, ...record._changes };
    record.dirty = wasDirty;
    if (typeof record._setEvalContext === "function") {
        record._setEvalContext();
    }
}
