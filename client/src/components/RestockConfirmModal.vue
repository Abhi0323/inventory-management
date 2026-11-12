<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" @click="close">
        <div class="modal-container" role="dialog" aria-modal="true" :aria-label="t('restocking.modal.title')" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">{{ t('restocking.modal.title') }}</h3>
            <button class="close-button" :aria-label="t('restocking.modal.close')" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <p class="modal-summary">{{ t('restocking.modal.summary') }}</p>

            <div class="summary-grid">
              <div class="info-item">
                <div class="info-label">{{ t('restocking.modal.total') }}</div>
                <div class="info-value">{{ formatMoney(total) }}</div>
              </div>
              <div class="info-item">
                <div class="info-label">{{ t('restocking.modal.budget') }}</div>
                <div class="info-value">{{ formatMoney(budget) }}</div>
              </div>
              <div class="info-item">
                <div class="info-label">{{ t('restocking.modal.expectedDelivery') }}</div>
                <div class="info-value">{{ expectedDelivery }}</div>
              </div>
            </div>

            <div class="items-list">
              <div v-for="item in items" :key="item.sku" class="line-item">
                <div class="line-main">
                  <span class="line-name">{{ translateProductName(item.name) }}</span>
                  <span class="line-sku">{{ item.sku }}</span>
                </div>
                <div class="line-meta">
                  {{ item.quantity }} &times; {{ formatMoney(item.unit_cost) }}
                  = <strong>{{ formatMoney(item.quantity * item.unit_cost) }}</strong>
                </div>
              </div>
            </div>

            <div v-if="error" class="modal-error" role="alert">{{ error }}</div>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" :disabled="submitting" @click="close">
              {{ t('restocking.modal.cancel') }}
            </button>
            <button class="btn-primary" :disabled="submitting" @click="emit('confirm')">
              {{ submitting ? t('restocking.modal.submitting') : t('restocking.modal.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { useI18n } from '../composables/useI18n'

const { t, currentCurrency, translateProductName } = useI18n()

defineProps({
  isOpen: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  budget: { type: Number, default: 0 },
  expectedDelivery: { type: String, default: '' },
  submitting: { type: Boolean, default: false },
  error: { type: String, default: null }
})

const emit = defineEmits(['confirm', 'close'])

const close = () => emit('close')

const formatMoney = (value) => {
  const symbol = currentCurrency.value === 'JPY' ? '¥' : '$'
  return `${symbol}${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 640px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.modal-summary {
  color: #64748b;
  font-size: 0.875rem;
  margin: 0 0 1.25rem 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 1rem;
  color: #0f172a;
  font-weight: 600;
}

.items-list {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  max-height: 260px;
  overflow-y: auto;
}

.line-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #f1f5f9;
}

.line-item:last-child {
  border-bottom: none;
}

.line-main {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  min-width: 0;
}

.line-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
}

.line-sku {
  font-size: 0.75rem;
  color: #64748b;
  font-family: 'Monaco', 'Courier New', monospace;
}

.line-meta {
  font-size: 0.813rem;
  color: #64748b;
  white-space: nowrap;
}

.line-meta strong {
  color: #0f172a;
}

.modal-error {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 0.875rem;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover:not(:disabled) {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #2563eb;
  border: 1px solid #2563eb;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.btn-secondary:disabled,
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
