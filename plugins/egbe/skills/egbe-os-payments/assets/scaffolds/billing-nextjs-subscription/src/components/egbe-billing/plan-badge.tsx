type PlanBadgeProps = {
  plan: string;
  warning?: boolean;
};

export function PlanBadge({ plan, warning = false }: PlanBadgeProps) {
  return (
    <span
      data-billing-plan-badge
      data-warning={warning || undefined}
      aria-label={`Current plan: ${plan}`}
    >
      {plan}
    </span>
  );
}
