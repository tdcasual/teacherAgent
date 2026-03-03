import SettingsModal from './SettingsModal'
import ModelSettingsPage from './ModelSettingsPage'

type TeacherSettingsPanelProps = {
  open: boolean
  onClose: () => void
  apiBase: string
  onApiBaseChange: (value: string) => void
}

const SETTINGS_SECTIONS: Array<{ id: string; label: string }> = [
  { id: 'model-settings', label: '模型设置' },
]

export default function TeacherSettingsPanel({
  open,
  onClose,
  apiBase,
  onApiBaseChange,
}: TeacherSettingsPanelProps) {
  return (
    <SettingsModal
      open={open}
      onClose={onClose}
      sections={SETTINGS_SECTIONS}
      activeSection="model-settings"
      onSectionChange={() => {}}
    >
      <ModelSettingsPage apiBase={apiBase} onApiBaseChange={onApiBaseChange} />
    </SettingsModal>
  )
}
