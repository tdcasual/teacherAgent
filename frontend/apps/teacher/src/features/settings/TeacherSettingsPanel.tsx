import RoutingPage, { type RoutingSection } from '../routing/RoutingPage'
import { isRoutingSection } from '../routing/routingSections'
import SettingsModal from './SettingsModal'

type TeacherSettingsPanelProps = {
  open: boolean
  onClose: () => void
  settingsSection: RoutingSection
  onSettingsSectionChange: (value: RoutingSection) => void
  apiBase: string
  onApiBaseChange: (value: string) => void
  onDirtyChange: (dirty: boolean) => void
  settingsLegacyFlat: boolean
}

const SETTINGS_SECTIONS: Array<{ id: RoutingSection; label: string }> = [
  { id: 'general', label: '通用' },
  { id: 'providers', label: 'Provider' },
  { id: 'channels', label: '渠道' },
  { id: 'rules', label: '路由规则' },
  { id: 'simulate', label: '仿真' },
  { id: 'history', label: '版本历史' },
]

export default function TeacherSettingsPanel({
  open,
  onClose,
  settingsSection,
  onSettingsSectionChange,
  apiBase,
  onApiBaseChange,
  onDirtyChange,
  settingsLegacyFlat,
}: TeacherSettingsPanelProps) {
  return (
    <SettingsModal
      open={open}
      onClose={onClose}
      sections={SETTINGS_SECTIONS}
      activeSection={settingsSection}
      onSectionChange={(id) => {
        if (isRoutingSection(id)) onSettingsSectionChange(id)
      }}
    >
      <RoutingPage
        apiBase={apiBase}
        onApiBaseChange={onApiBaseChange}
        onDirtyChange={onDirtyChange}
        section={settingsSection}
        legacyFlat={settingsLegacyFlat}
      />
    </SettingsModal>
  )
}
