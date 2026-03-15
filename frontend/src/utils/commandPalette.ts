export const OPEN_COMMAND_PALETTE_EVENT = 'researchhub:open-command-palette';

export const openCommandPalette = () => {
  window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT));
};
