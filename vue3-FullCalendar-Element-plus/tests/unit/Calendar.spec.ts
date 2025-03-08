import { mount } from '@vue/test-utils'
import { vi } from 'vitest'
import { ElButton, ElSelect, ElOption, ElDatePicker, ElCard, ElInput, ElForm, ElFormItem, ElDrawer } from 'element-plus'
import Calendar from '../../src/components/Calendar/Calendar.vue'

const globalComponents = {
  components: {
    ElButton,
    ElSelect, 
    ElOption,
    ElDatePicker,
    ElCard,
    ElInput,
    ElForm,
    ElFormItem,
    ElDrawer
  },
  config: {
    globalProperties: {
      $icons: {
        ArrowLeftBold: 'arrow-left-bold',
        ArrowRightBold: 'arrow-right-bold',
        Plus: 'plus'
      }
    }
  }
}

describe('Calendar.vue', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-type': 'application/json' }
      }))
    )
  })

  afterEach(() => {
    vi.clearAllMocks()
  })
  it('renders calendar container', () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    expect(wrapper.find('.calendar-container').exists()).toBe(true)
  })

  it('displays current month and year', () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    const today = new Date()
    const expectedText = `${today.toLocaleString('default', { month: 'long' })} ${today.getFullYear()}`
    expect(wrapper.find('.calendar-header').text()).toContain(expectedText)
  })

  it('emits date-click event when a date is clicked', async () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    await wrapper.find('.calendar-day:not(.disabled)').trigger('click')
    expect(wrapper.emitted('date-click')).toBeTruthy()
  })

  it('navigates to previous month when prev button is clicked', async () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    const initialMonth = wrapper.find('.calendar-header').text()
    await wrapper.find('.prev-month-button').trigger('click')
    const newMonth = wrapper.find('.calendar-header').text()
    expect(newMonth).not.toBe(initialMonth)
  })

  it('navigates to next month when next button is clicked', async () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    const initialMonth = wrapper.find('.calendar-header').text()
    await wrapper.find('.next-month-button').trigger('click')
    const newMonth = wrapper.find('.calendar-header').text()
    expect(newMonth).not.toBe(initialMonth)
  })

  it('displays loading state while fetching events', async () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    expect(wrapper.find('.loading-spinner').exists()).toBe(true)
  })

  it('hides loading state after events are fetched', async () => {
    const wrapper = mount(Calendar, {
      global: globalComponents
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.loading-spinner').exists()).toBe(false)
  })
})
