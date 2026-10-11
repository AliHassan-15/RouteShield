// PDF transcription for explanatory display ONLY. Python alone classifies risk.
export const WIND_RULE_COPY = [
  { aboveWeight: null, text: 'Wind of 55 mph or more is No Travel for any load.', wind: '≥55 mph', effect: 'No Travel' },
  { aboveWeight: 30_000, text: 'Above 30,000 lb: winds of 45 to 54 mph become No Travel.', wind: '45–54 mph', effect: 'No Travel' },
  { aboveWeight: 40_000, text: 'Above 40,000 lb: winds of 35 to 44 mph become Severe.', wind: '35–44 mph', effect: 'Severe' },
] as const;
