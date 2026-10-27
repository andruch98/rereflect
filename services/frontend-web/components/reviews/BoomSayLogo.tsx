import Image from 'next/image';

export function BoomSayLogo({ mark = false, white = false }: { mark?: boolean; white?: boolean }) {
  const kind = mark ? 'mark' : 'wordmark';
  const dimensions = mark ? { width: 44, height: 24 } : { width: 156, height: 35 };
  if (white) return <Image src={`/brand/boomsay-${kind}-white.svg`} alt="BoomSay" {...dimensions} />;
  return <>
    <Image src={`/brand/boomsay-${kind}-blue.svg`} alt="BoomSay" {...dimensions} className="dark:hidden" />
    <Image src={`/brand/boomsay-${kind}-white.svg`} alt="BoomSay" {...dimensions} className="hidden dark:block" />
  </>;
}
