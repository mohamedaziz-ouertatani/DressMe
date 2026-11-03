import type { Language } from '../api/types'

// Playful lines shown while the try-on works (ui/TryOnProgress.tsx), one every
// few seconds in a shuffled order, so a whole outfit (3 pieces, ~4 min) never
// shows the same line twice. Same count in every language is not required.
export const QUIPS: Record<Language, string[]> = {
  en: [
    'Ironing out the wrinkles…', 'Asking the pixels to hold still…', 'Matching the sleeves to your arms…',
    'Checking it isn’t too baggy…', 'Teaching the fabric how you stand…', 'Smoothing the creases, no iron needed…',
    'Measuring twice, stitching once…', 'Keeping the colour true…', 'Striking your best pose for you…',
    'Getting the hem just right…', 'Snipping the loose threads…', 'Counting the buttons. Twice.',
    'Finding where your shoulders end…', 'Convincing the collar to sit flat…', 'Lining up the seams…',
    'Pinning everything in place…', 'Steaming out the last creases…', 'Asking the mirror for a second opinion…',
    'Folding the cuffs, neatly…', 'Choosing the right amount of drape…', 'Letting the fabric fall naturally…',
    'Checking the fit from every angle…', 'Untangling a very stubborn thread…', 'Tucking in what needs tucking…',
    'Adjusting the waist, a tiny bit…', 'Sweeping up the fabric scraps…', 'Warming up the sewing machine…',
    'Threading the needle (third try)…', 'Comparing shades in better light…', 'Making sure the pockets are pockets…',
    'Removing the price tag…', 'Shaking the friperie dust off…', 'Giving it a quick lint roll…',
    'Rehearsing your runway walk…', 'Calling the tailor back from lunch…', 'Ironing… carefully, it’s a good one…',
    'Telling the shadows where to fall…', 'Checking the light on the fabric…', 'Straightening the shoulders…',
    'Giving the folds some personality…', 'Making the zip behave…', 'Gently stretching the knit…',
    'Matching the stripes at the seams…', 'Practising a confident smile for you…', 'Debating sleeves: rolled or not?',
    'Taking it off the hanger for you…', 'Making room in the fitting room…', 'Turning the mirror to the light…',
    'Brushing off a stray thread…', 'Making sure nothing is see-through…', 'Measuring the inside leg…',
    'Picking the fabric up off the floor…', 'Checking the label says your size…', 'Asking the GPU to hurry, politely…',
    'Pressing the pleats…', 'Fixing a wobbly hem…', 'Making it look worn, not borrowed…',
    'Finding the perfect fold at the ankle…', 'Letting the fabric settle…', 'Taking one last look in the mirror…',
  ],
  fr: [
    'On repasse les plis…', 'On demande aux pixels de ne plus bouger…', 'On ajuste les manches à tes bras…',
    'On vérifie que ce n’est pas trop large…', 'On apprend au tissu comment tu te tiens…', 'On lisse les plis, sans fer à repasser…',
    'Mesurer deux fois, coudre une fois…', 'On garde la vraie couleur…', 'On prend la pose à ta place…',
    'On ajuste l’ourlet…', 'On coupe les fils qui dépassent…', 'On compte les boutons. Deux fois.',
    'On cherche où finissent tes épaules…', 'On convainc le col de rester à plat…', 'On aligne les coutures…',
    'On épingle tout en place…', 'Un coup de vapeur sur les derniers plis…', 'On demande l’avis du miroir…',
    'On replie les poignets, proprement…', 'On choisit le bon tombé…', 'On laisse le tissu tomber naturellement…',
    'On vérifie la coupe sous tous les angles…', 'On démêle un fil très têtu…', 'On rentre ce qui doit être rentré…',
    'On ajuste la taille, un tout petit peu…', 'On ramasse les chutes de tissu…', 'On fait chauffer la machine à coudre…',
    'On enfile l’aiguille (troisième essai)…', 'On compare les teintes à la lumière…', 'On vérifie que les poches sont des poches…',
    'On enlève l’étiquette du prix…', 'On secoue la poussière de la friperie…', 'Un petit coup de brosse anti-peluches…',
    'On répète ton défilé…', 'On rappelle le tailleur de sa pause déjeuner…', 'On repasse… doucement, c’est une belle pièce…',
    'On dit aux ombres où tomber…', 'On regarde la lumière sur le tissu…', 'On redresse les épaules…',
    'On donne du caractère aux plis…', 'On calme la fermeture éclair…', 'On détend doucement la maille…',
    'On aligne les rayures aux coutures…', 'On prépare un sourire assuré pour toi…', 'Manches retroussées ou pas ? On débat…',
    'On décroche le cintre pour toi…', 'On libère la cabine d’essayage…', 'On tourne le miroir vers la lumière…',
    'On enlève un fil qui traîne…', 'On vérifie que rien n’est transparent…', 'On mesure l’entrejambe…',
    'On ramasse le tissu tombé par terre…', 'On vérifie que l’étiquette dit ta taille…', 'On demande poliment au GPU de se presser…',
    'On marque les plis au fer…', 'On rattrape un ourlet bancal…', 'On fait en sorte que ça ait l’air à toi, pas emprunté…',
    'On cherche le pli parfait à la cheville…', 'On laisse le tissu se poser…', 'Un dernier regard dans le miroir…',
  ],
  ar: [
    'نكوي التجاعيد…', 'نطلب من البكسلات أن تثبت في مكانها…', 'نضبط الأكمام على ذراعيك…',
    'نتأكد أنها ليست واسعة جدا…', 'نعلّم القماش كيف تقف…', 'نملّس الثنيات بلا مكواة…',
    'نقيس مرتين ونخيط مرة واحدة…', 'نحافظ على اللون الحقيقي…', 'نتخذ أفضل وضعية بدلا عنك…',
    'نضبط طرف القماش بإتقان…', 'نقص الخيوط الزائدة…', 'نعدّ الأزرار. مرتين.',
    'نبحث أين تنتهي كتفاك…', 'نقنع الياقة أن تبقى مستوية…', 'نحاذي الخياطات…',
    'نثبّت كل شيء بالدبابيس…', 'بخار خفيف على آخر الثنيات…', 'نطلب رأي المرآة…',
    'نطوي الأكمام بعناية…', 'نختار الانسدال المناسب…', 'نترك القماش ينسدل بشكل طبيعي…',
    'نتحقق من المقاس من كل الزوايا…', 'نفك خيطا عنيدا جدا…', 'ندخل ما يجب إدخاله…',
    'نضبط الخصر قليلا…', 'نجمع بقايا القماش…', 'نسخّن آلة الخياطة…',
    'ندخل الخيط في الإبرة (المحاولة الثالثة)…', 'نقارن الدرجات في ضوء أفضل…', 'نتأكد أن الجيوب جيوب فعلا…',
    'نزيل بطاقة السعر…', 'ننفض غبار محل الملابس المستعملة…', 'تنظيف سريع من الوبر…',
    'نتمرن على مشيتك على المنصة…', 'نستدعي الخياط من استراحة الغداء…', 'نكوي… بحذر، إنها قطعة جميلة…',
    'نخبر الظلال أين تسقط…', 'نتأمل الضوء على القماش…', 'نعدّل الكتفين…',
    'نمنح الثنيات بعض الشخصية…', 'نروّض السحّاب…', 'نمدّ التريكو بلطف…',
    'نطابق الخطوط عند الخياطات…', 'نحضّر لك ابتسامة واثقة…', 'أكمام مطوية أم لا؟ نتناقش…',
    'ننزل العلّاقة من أجلك…', 'نفسح المكان في غرفة القياس…', 'ندير المرآة نحو الضوء…',
    'نزيل خيطا شاردا…', 'نتأكد أن لا شيء شفاف…', 'نقيس طول الساق…',
    'نلتقط القماش من الأرض…', 'نتأكد أن البطاقة تحمل مقاسك…', 'نطلب من المعالج الرسومي أن يسرع، بلطف…',
    'نكوي الطيّات…', 'نصلح طرفا مائلا…', 'نجعلها تبدو ملكك، لا مستعارة…',
    'نبحث عن الثنية المثالية عند الكاحل…', 'نترك القماش يستقر…', 'نظرة أخيرة في المرآة…',
  ],
}

/** A random order of the line numbers 0..n-1 (Fisher-Yates). */
export function shuffled(n: number): number[] {
  const order = Array.from({ length: n }, (_, i) => i)
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  return order
}
