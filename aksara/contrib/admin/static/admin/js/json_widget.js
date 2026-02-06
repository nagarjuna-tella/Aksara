/**
 * JSON Widget JavaScript
 * Version: 0.5.9
 * 
 * Provides JSON formatting and validation for JSONAdminWidget
 * Features:
 * - Auto-format on blur
 * - Real-time validation  
 * - Keyboard shortcuts (Ctrl+Shift+F)
 * - Copy/paste handling
 */

/**
 * Format JSON in a textarea
 * @param {string} fieldId - ID of the textarea element
 * @param {boolean} showFeedback - Whether to show visual feedback
 */
function formatJSON(fieldId, showFeedback = true) {
    const textarea = document.getElementById(fieldId);
    const errorDiv = document.getElementById(fieldId + '_error');
    const infoDiv = document.getElementById(fieldId + '_info');
    
    if (!textarea) return false;
    
    // Skip empty values
    if (!textarea.value.trim()) {
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }
        textarea.classList.remove('error');
        return true;
    }
    
    try {
        // Parse and re-stringify with formatting
        const parsed = JSON.parse(textarea.value);
        const formatted = JSON.stringify(parsed, null, 2);
        
        // Only update if different (preserves cursor position otherwise)
        if (textarea.value !== formatted) {
            textarea.value = formatted;
        }
        
        // Clear any error
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }
        
        // Show info about JSON structure
        if (infoDiv) {
            const info = getJSONInfo(parsed);
            infoDiv.textContent = info;
            infoDiv.style.display = 'block';
        }
        
        // Visual feedback
        textarea.classList.remove('error');
        if (showFeedback) {
            textarea.classList.add('success-flash');
            setTimeout(() => textarea.classList.remove('success-flash'), 300);
        }
        
        return true;
        
    } catch (error) {
        // Show error message
        if (errorDiv) {
            errorDiv.style.display = 'block';
            errorDiv.textContent = `Invalid JSON: ${error.message}`;
        }
        
        textarea.classList.add('error');
        
        if (showFeedback) {
            // Flash error
            setTimeout(() => {
                textarea.classList.remove('error');
                textarea.classList.add('error'); // Re-add to trigger animation
            }, 100);
        }
        
        return false;
    }
}

/**
 * Get info about JSON structure
 * @param {any} parsed - Parsed JSON value
 * @returns {string} - Info string
 */
function getJSONInfo(parsed) {
    if (Array.isArray(parsed)) {
        return `Array with ${parsed.length} item${parsed.length !== 1 ? 's' : ''}`;
    } else if (typeof parsed === 'object' && parsed !== null) {
        const keys = Object.keys(parsed);
        return `Object with ${keys.length} key${keys.length !== 1 ? 's' : ''}`;
    } else {
        return typeof parsed;
    }
}

/**
 * Validate JSON on form submit
 */
function validateJSONFields() {
    const jsonTextareas = document.querySelectorAll('textarea[data-json-widget="true"]');
    let allValid = true;
    let firstInvalid = null;
    
    jsonTextareas.forEach(textarea => {
        const errorDiv = document.getElementById(textarea.id + '_error');
        
        // Skip validation if field is empty and not required
        if (!textarea.value.trim() && !textarea.required) {
            if (errorDiv) {
                errorDiv.style.display = 'none';
            }
            textarea.classList.remove('error');
            return;
        }
        
        try {
            JSON.parse(textarea.value);
            textarea.classList.remove('error');
            if (errorDiv) {
                errorDiv.style.display = 'none';
                errorDiv.textContent = '';
            }
        } catch (error) {
            allValid = false;
            textarea.classList.add('error');
            if (errorDiv) {
                errorDiv.style.display = 'block';
                errorDiv.textContent = `Invalid JSON: ${error.message}`;
            }
            
            // Track first invalid field
            if (!firstInvalid) {
                firstInvalid = textarea;
            }
        }
    });
    
    // Scroll to first error
    if (firstInvalid) {
        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstInvalid.focus();
    }
    
    return allValid;
}

/**
 * Initialize JSON widgets
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add keyboard shortcut for formatting (Ctrl+Shift+F)
    document.addEventListener('keydown', function(e) {
        // Ctrl+Shift+F or Cmd+Shift+F
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
            const activeElement = document.activeElement;
            
            if (activeElement && activeElement.dataset.jsonWidget === 'true') {
                e.preventDefault();
                formatJSON(activeElement.id);
            }
        }
    });
    
    // Add validation to form submit
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateJSONFields()) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Auto-validate on blur
    const jsonTextareas = document.querySelectorAll('textarea[data-json-widget="true"]');
    jsonTextareas.forEach(textarea => {
        textarea.addEventListener('blur', function() {
            formatJSON(this.id, false);
        });
        
        // Handle paste - auto format after paste
        textarea.addEventListener('paste', function() {
            setTimeout(() => {
                formatJSON(this.id, true);
            }, 0);
        });
    });
});
