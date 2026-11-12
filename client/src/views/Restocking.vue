<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successOrder" class="success-banner" role="status">
        <div class="success-text">
          <strong>{{ t('restocking.successTitle') }}</strong>
          <span>{{ t('restocking.successMessage', { orderNumber: successOrder.order_number, date: formatDate(successOrder.expected_delivery) }) }}</span>
        </div>
        <div class="success-actions">
          <router-link to="/orders" class="success-link">{{ t('restocking.viewOrder') }}</router-link>
          <button class="link-button" @click="successOrder = null">{{ t('restocking.dismiss') }}</button>
        </div>
      </div>

      <div class="card budget-card">
        <label class="budget-label" for="restock-budget">{{ t('restocking.budgetLabel') }}</label>
        <div class="budget-row">
          <input
            id="restock-budget"
            v-model.number="budget"
            class="budget-slider"
            type="range"
            min="0"
            :max="maxBudget"
            :step="STEP"
            :disabled="maxBudget === 0"
            :aria-valuetext="formatMoney(budget)"
          />
          <div class="budget-readout">{{ formatMoney(budget) }}</div>
        </div>
        <div class="budget-hint">{{ t('restocking.budgetHint') }}</div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.stats.budget') }}</div>
          <div class="stat-value">{{ formatMoney(budget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.plannedSpend') }}</div>
          <div class="stat-value">{{ formatMoney(plannedSpend) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.stats.remaining') }}</div>
          <div class="stat-value">{{ formatMoney(remaining) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.stats.itemsRecommended') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header header-row">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
          <button
            class="btn-primary"
            :disabled="recommendations.length === 0 || submitting || successOrder !== null"
            @click="openModal"
          >
            {{ t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ shortfallItems.length === 0 ? t('restocking.noShortfall') : t('restocking.empty') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.shortfall') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.sku">
                <td><strong>{{ rec.sku }}</strong></td>
                <td>{{ translateProductName(rec.name) }}</td>
                <td>
                  <span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span>
                </td>
                <td class="num">{{ rec.shortfall }}</td>
                <td class="num"><strong>{{ rec.quantity }}</strong></td>
                <td class="num">{{ formatMoney(rec.unit_cost) }}</td>
                <td class="num"><strong>{{ formatMoney(rec.lineTotal) }}</strong></td>
                <td class="num">{{ t('restocking.days', { count: rec.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <RestockConfirmModal
      :is-open="showModal"
      :items="orderItems"
      :total="plannedSpend"
      :budget="budget"
      :expected-delivery="expectedDeliveryLabel"
      :submitting="submitting"
      :error="submitError"
      @confirm="submitOrder"
      @close="closeModal"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import RestockConfirmModal from '../components/RestockConfirmModal.vue'

const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

const STEP = 500
const TREND_PRIORITY = { increasing: 0, stable: 1, decreasing: 2 }

const loading = ref(true)
const error = ref(null)
const forecasts = ref([])
const budget = ref(0)

const showModal = ref(false)
const submitting = ref(false)
const submitError = ref(null)
const successOrder = ref(null)

const toCents = (value) => Math.round(Number(value) * 100)

// Items with a positive shortfall, sorted by trend priority then shortfall cost desc
const shortfallItems = computed(() => {
  return forecasts.value
    .map(f => {
      const shortfall = f.forecasted_demand - f.current_demand
      return {
        sku: f.item_sku,
        name: f.item_name,
        trend: f.trend,
        unit_cost: f.unit_cost,
        lead_time_days: f.lead_time_days,
        shortfall,
        shortfallCents: shortfall * toCents(f.unit_cost)
      }
    })
    .filter(i => i.shortfall > 0 && toCents(i.unit_cost) > 0)
    .sort((a, b) => {
      const pa = TREND_PRIORITY[a.trend] ?? 3
      const pb = TREND_PRIORITY[b.trend] ?? 3
      if (pa !== pb) return pa - pb
      return b.shortfallCents - a.shortfallCents
    })
})

const maxBudget = computed(() => {
  const totalCents = shortfallItems.value.reduce((sum, i) => sum + i.shortfallCents, 0)
  return Math.ceil(totalCents / 100 / STEP) * STEP
})

// Greedy fill in integer cents to avoid floating point drift
const recommendations = computed(() => {
  let remainingCents = Math.max(0, Math.round(budget.value * 100))
  const result = []
  for (const item of shortfallItems.value) {
    const costCents = toCents(item.unit_cost)
    const quantity = Math.min(item.shortfall, Math.floor(remainingCents / costCents))
    if (quantity > 0) {
      const lineCents = quantity * costCents
      remainingCents -= lineCents
      result.push({ ...item, quantity, lineTotal: lineCents / 100 })
    }
  }
  return result
})

const plannedSpend = computed(() => {
  const cents = recommendations.value.reduce((sum, r) => sum + Math.round(r.lineTotal * 100), 0)
  return cents / 100
})

const remaining = computed(() => Math.round((budget.value - plannedSpend.value) * 100) / 100)

const orderItems = computed(() =>
  recommendations.value.map(r => ({
    sku: r.sku,
    name: r.name,
    quantity: r.quantity,
    unit_cost: r.unit_cost
  }))
)

const expectedDeliveryLabel = computed(() => {
  if (recommendations.value.length === 0) return ''
  const maxLead = Math.max(...recommendations.value.map(r => r.lead_time_days))
  const d = new Date()
  d.setDate(d.getDate() + maxLead)
  return formatDate(d)
})

const formatMoney = (value) => {
  const symbol = currentCurrency.value === 'JPY' ? '¥' : '$'
  return `${symbol}${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

const formatDate = (value) => {
  // Parse date-only ISO strings as local midnight; new Date('YYYY-MM-DD') is UTC and shifts a day west of UTC
  const date = value instanceof Date
    ? value
    : new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value)
  if (isNaN(date.getTime())) return ''
  const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
  return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
}

const loadData = async () => {
  try {
    loading.value = true
    error.value = null
    forecasts.value = await api.getDemandForecasts()
    budget.value = Math.round(maxBudget.value / 2 / STEP) * STEP
  } catch (err) {
    console.error('Failed to load demand forecasts:', err)
    error.value = t('restocking.loadError') + ': ' + err.message
  } finally {
    loading.value = false
  }
}

// After a successful order, changing the budget starts a new plan and re-enables Place Order
watch(budget, () => { successOrder.value = null })

const openModal = () => {
  if (recommendations.value.length === 0 || submitting.value || successOrder.value) return
  submitError.value = null
  showModal.value = true
}

const closeModal = () => {
  if (submitting.value) return
  showModal.value = false
}

const submitOrder = async () => {
  if (submitting.value || orderItems.value.length === 0) return
  submitting.value = true
  submitError.value = null
  try {
    const order = await api.createRestockOrder({
      items: orderItems.value.map(({ sku, quantity }) => ({ sku, quantity })),
      budget: budget.value
    })
    successOrder.value = order
    showModal.value = false
  } catch (err) {
    const detail = err.response?.data?.detail
    submitError.value = typeof detail === 'string' ? detail : t('restocking.submitError')
  } finally {
    submitting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-label {
  display: block;
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.75rem;
}

.budget-row {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.budget-readout {
  min-width: 110px;
  text-align: right;
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-hint {
  margin-top: 0.5rem;
  font-size: 0.813rem;
  color: #64748b;
}

.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.budget-slider:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #3b82f6;
  border: 2px solid white;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.3);
  cursor: pointer;
}

.budget-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  border: 2px solid white;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.3);
  cursor: pointer;
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
}

.budget-slider:focus-visible::-webkit-slider-thumb {
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.budget-slider:focus-visible::-moz-range-thumb {
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.num {
  text-align: right;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #2563eb;
  border: 1px solid #2563eb;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  color: white;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.success-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  color: #166534;
  font-size: 0.875rem;
}

.success-text {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.success-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-shrink: 0;
}

.success-link {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}

.success-link:hover {
  text-decoration: underline;
}

.link-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.875rem;
}

.link-button:hover {
  color: #0f172a;
}
</style>
