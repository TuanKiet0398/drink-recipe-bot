// Shared class strings for the admin panel, so pages don't repeat long
// Tailwind chains. Landing and login keep their own styling.

export const card = "rounded-xl border border-admin-border bg-white shadow-admin-card";
export const pageTitle = "text-xl font-bold text-admin-fg";
export const pageDescription = "mt-1 text-[13.5px] text-admin-muted";
export const sectionLabel = "text-[11px] font-bold uppercase tracking-wide text-admin-muted";
export const fieldLabel = "flex flex-col gap-1 text-[13px] font-semibold text-admin-fg";
export const hint = "text-xs font-normal text-admin-muted";
export const emptyCell = "py-8 text-center text-[13.5px] text-admin-muted";

const btnBase =
  "rounded-lg px-3.5 py-2 text-[13px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";
export const btnPrimary = `${btnBase} bg-admin-primary text-white hover:bg-admin-primary-dark`;
export const btnSecondary = `${btnBase} border border-admin-border bg-white text-admin-fg-2 hover:bg-admin-bg`;
export const btnDanger = `${btnBase} border border-admin-danger-border bg-white text-admin-danger hover:bg-admin-danger-light`;

const ghostBase = "rounded-md px-2 py-1 text-[12.5px] font-semibold transition-colors disabled:opacity-50";
export const btnGhost = `${ghostBase} text-admin-fg-2 hover:bg-admin-bg`;
export const btnGhostPrimary = `${ghostBase} text-admin-primary hover:bg-admin-primary-light`;
export const btnGhostDanger = `${ghostBase} text-admin-danger hover:bg-admin-danger-light`;

export const input =
  "rounded-lg border border-admin-border bg-white px-3 py-2 text-[13.5px] font-normal text-admin-fg focus:border-admin-primary focus:outline-none focus:ring-[3px] focus:ring-admin-primary/20 disabled:bg-admin-bg disabled:text-admin-muted";

const badgeBase = "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold";
export const badgeNeutral = `${badgeBase} bg-admin-bg text-admin-fg-2`;
export const badgeSuccess = `${badgeBase} bg-admin-primary-light text-admin-primary-dark`;
export const badgeDanger = `${badgeBase} bg-admin-danger-light text-admin-danger`;
export const badgeWarning = `${badgeBase} bg-amber-50 text-amber-800`;

const alertBase = "rounded-lg px-3 py-2 text-[13px]";
export const alertError = `${alertBase} bg-admin-danger-light text-admin-danger`;
export const alertSuccess = `${alertBase} bg-admin-primary-light text-admin-primary-dark`;
export const alertWarning = `${alertBase} bg-amber-50 text-amber-800`;
