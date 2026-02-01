/**
 * JSON Widget JavaScript
 * 
 * Provides JSON formatting and validation for JSONAdminWidget
 */

/**
 * Format JSON in a textarea
 * @param {string} fieldId - ID of the textarea element
 */
function formatJSON(fieldId) {
    const textarea = document.getElementById(fieldId);
    const errorDiv = document.getElementById(fieldId + '_error');
    
    if (!textarea) return;
    
    try {
        // Parse and re-stringify with formatting
        const parsed = JSON.parse(textarea.value);
        textarea.value = JSON.stringify(parsed, null, 2);
        
        // Clear any error
        if (errorDiv) {
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
        }
        
        // Visual feedback
        textarea.classList.remove('error');
        textarea.classList.add('success-flash');
        setTimeout(() => textarea.classList.remove('success-flash'), 300);
        
    } catch (error) {
        // Show error message
        if (errorDiv) {
            errorDiv.style.display = 'block';
            errorDiv.textContent = `Invalid JSON: ${error.message}`;
        }
        
        textarea.classList.add('error');
        
        // Flash error
        setTimeout(() => textarea.classList.remove('error'), 2000);
    }
}

/**
 * Validate JSON on form submit
 */
function validateJSONFields() {
    const jsonTextareas = document.querySelectorAll('textarea[data-json-widget="true"]');
    let allValid = true;
    
    jsonTextareas.forEach(textarea => {
        const errorDiv = document.getElementById(textarea.id + '_error');
        
        // Skip validation if field is empty and not required
        if (!textarea.value.trim() && !textarea.required) {
            if (errorDiv) {
                errorDiv.style.display = 'none';
            }
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
            
            // Scroll to first error
            if (allValid === false) {
                textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });
    
    return allValid;
}

/**
 * Add keyboard shortcut for formatting (Ctrl+Shift+F)
 */
document.addEventListener('DOMContentLoaded', function() {
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
});
