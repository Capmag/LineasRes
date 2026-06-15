/**
 * Toast Manager - Sistema de notificaciones sin alertas nativas
 * Reemplaza alert() con toasts Bootstrap profesionales
 */

class ToastManager {
    constructor() {
        this.container = document.body;
        this.toasts = [];
    }

    /**
     * Crea un toast de éxito
     */
    success(message, duration = 3000) {
        this.show(message, 'success', duration);
    }

    /**
     * Crea un toast de error
     */
    error(message, duration = 4000) {
        this.show(message, 'danger', duration);
    }

    /**
     * Crea un toast de información
     */
    info(message, duration = 3000) {
        this.show(message, 'info', duration);
    }

    /**
     * Crea un toast de advertencia
     */
    warning(message, duration = 3000) {
        this.show(message, 'warning', duration);
    }

    /**
     * Muestra un toast personalizado
     */
    show(message, type = 'info', duration = 3000) {
        // Crear contenedor si no existe
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            `;
            this.container.appendChild(toastContainer);
        }

        // Crear elemento toast
        const toastId = 'toast-' + Date.now() + Math.random();
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `alert alert-${type} alert-dismissible fade show`;
        toast.style.cssText = `
            min-width: 300px;
            max-width: 400px;
            pointer-events: auto;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: none;
            animation: slideIn 0.3s ease-out;
        `;

        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <span class="toast-indicator-${type}"></span>
                <span style="flex: 1; font-weight: 600;">${message}</span>
            </div>
            <button type="button" class="btn-close" onclick="document.getElementById('${toastId}').remove()" aria-label="Close"></button>
        `;

        toastContainer.appendChild(toast);
        this.toasts.push(toastId);

        // Auto-remover después del duration
        setTimeout(() => {
            const element = document.getElementById(toastId);
            if (element) {
                element.classList.remove('show');
                setTimeout(() => element.remove(), 150);
            }
        }, duration);
    }

    /**
     * Limpia todos los toasts
     */
    clear() {
        const container = document.getElementById('toastContainer');
        if (container) container.innerHTML = '';
        this.toasts = [];
    }
}

// Agregar estilos de animación
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }

    #toastContainer .alert {
        animation: slideIn 0.3s ease-out;
    }

    #toastContainer .alert.removing {
        animation: slideOut 0.3s ease-out;
    }
`;
document.head.appendChild(style);

// Instancia global del ToastManager
const Toast = new ToastManager();
