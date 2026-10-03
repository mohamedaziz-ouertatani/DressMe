// Labels for every schema value (mappings/*.csv) in English, French and Arabic.
// Tickets print the label in the UI language plus a second line in the other
// script (Arabic under Latin, Latin under Arabic), like bilingual Tunisian tickets.
import type { Language } from '../api/types'

type Labels = Record<string, [en: string, fr: string, ar: string]>

export const CATEGORY_LABELS: Labels = {
  top: ['Top', 'Haut', 'قطعة علوية'],
  bottom: ['Bottom', 'Bas', 'قطعة سفلية'],
  dress: ['Dress', 'Robe', 'فستان'],
  outerwear: ['Outerwear', 'Veste & manteau', 'ملابس خارجية'],
  shoes: ['Shoes', 'Chaussures', 'أحذية'],
  bag: ['Bag', 'Sac', 'حقيبة'],
  accessory: ['Accessory', 'Accessoire', 'إكسسوار'],
  traditional: ['Traditional', 'Traditionnel', 'لباس تقليدي'],
  swimwear: ['Swimwear', 'Maillot', 'لباس سباحة'],
}

export const SUB_LABELS: Labels = {
  shirt: ['Shirt', 'Chemise', 'قميص'],
  sweater: ['Sweater', 'Pull', 'كنزة صوف'],
  sweatshirt: ['Sweatshirt', 'Sweat', 'سويت شيرت'],
  't-shirt': ['T-shirt', 'T-shirt', 'تيشيرت'],
  top: ['Top', 'Top', 'توب'],
  tunic: ['Tunic', 'Tunique', 'تونيك'],
  capris: ['Capris', 'Corsaire', 'سروال قصير'],
  jeans: ['Jeans', 'Jean', 'جينز'],
  leggings: ['Leggings', 'Legging', 'ليقنز'],
  shorts: ['Shorts', 'Short', 'شورت'],
  skirt: ['Skirt', 'Jupe', 'تنورة'],
  'track-pants': ['Track pants', 'Jogging', 'سروال رياضي'],
  trousers: ['Trousers', 'Pantalon', 'سروال'],
  dress: ['Dress', 'Robe', 'فستان'],
  jumpsuit: ['Jumpsuit', 'Combinaison', 'جمبسوت'],
  blazer: ['Blazer', 'Blazer', 'بليزر'],
  cape: ['Cape', 'Cape', 'كاب'],
  cardigan: ['Cardigan', 'Gilet', 'كارديغان'],
  coat: ['Coat', 'Manteau', 'معطف'],
  jacket: ['Jacket', 'Veste', 'جاكيت'],
  waistcoat: ['Waistcoat', 'Gilet sans manches', 'صدرية'],
  'casual-shoes': ['Casual shoes', 'Chaussures de ville', 'حذاء يومي'],
  flats: ['Flats', 'Ballerines', 'حذاء مسطح'],
  'flip-flops': ['Flip-flops', 'Tongs', 'شلاكة'],
  'formal-shoes': ['Formal shoes', 'Chaussures habillées', 'حذاء رسمي'],
  heels: ['Heels', 'Talons', 'كعب عالي'],
  sandals: ['Sandals', 'Sandales', 'صندل'],
  sneakers: ['Sneakers', 'Baskets', 'سبادري'],
  backpack: ['Backpack', 'Sac à dos', 'حقيبة ظهر'],
  clutch: ['Clutch', 'Pochette', 'كلاتش'],
  'duffel-bag': ['Duffel bag', 'Sac de voyage', 'حقيبة سفر'],
  handbag: ['Handbag', 'Sac à main', 'حقيبة يد'],
  'laptop-bag': ['Laptop bag', 'Sac ordinateur', 'حقيبة حاسوب'],
  'messenger-bag': ['Messenger bag', 'Besace', 'حقيبة كتف'],
  'waist-bag': ['Waist bag', 'Banane', 'حقيبة خصر'],
  belt: ['Belt', 'Ceinture', 'حزام'],
  bracelet: ['Bracelet', 'Bracelet', 'سوار'],
  brooch: ['Brooch', 'Broche', 'بروش'],
  cap: ['Cap', 'Casquette', 'كاسكيت'],
  cufflinks: ['Cufflinks', 'Boutons de manchette', 'أزرار أكمام'],
  earrings: ['Earrings', "Boucles d'oreilles", 'أقراط'],
  glasses: ['Glasses', 'Lunettes', 'نظارات'],
  gloves: ['Gloves', 'Gants', 'قفازات'],
  'hair-accessory': ['Hair accessory', 'Accessoire cheveux', 'إكسسوار شعر'],
  hat: ['Hat', 'Chapeau', 'قبعة'],
  'jewellery-set': ['Jewellery set', 'Parure', 'طقم مجوهرات'],
  necklace: ['Necklace', 'Collier', 'قلادة'],
  ring: ['Ring', 'Bague', 'خاتم'],
  scarf: ['Scarf', 'Foulard', 'وشاح'],
  sunglasses: ['Sunglasses', 'Lunettes de soleil', 'نظارات شمسية'],
  suspenders: ['Suspenders', 'Bretelles', 'حمالات'],
  tie: ['Tie', 'Cravate', 'ربطة عنق'],
  wallet: ['Wallet', 'Portefeuille', 'محفظة'],
  watch: ['Watch', 'Montre', 'ساعة'],
  'swim-shorts': ['Swim shorts', 'Short de bain', 'شورت سباحة'],
  swimsuit: ['Swimsuit', 'Maillot de bain', 'مايوه'],
  jebba: ['Jebba', 'Jebba', 'جبة'],
  kaftan: ['Kaftan', 'Caftan', 'قفطان'],
}

export const COLOUR_LABELS: Labels = {
  black: ['Black', 'Noir', 'أسود'],
  white: ['White', 'Blanc', 'أبيض'],
  cream: ['Cream', 'Crème', 'كريمي'],
  grey: ['Grey', 'Gris', 'رمادي'],
  beige: ['Beige', 'Beige', 'بيج'],
  brown: ['Brown', 'Marron', 'بني'],
  khaki: ['Khaki', 'Kaki', 'كاكي'],
  red: ['Red', 'Rouge', 'أحمر'],
  burgundy: ['Burgundy', 'Bordeaux', 'عنابي'],
  pink: ['Pink', 'Rose', 'وردي'],
  orange: ['Orange', 'Orange', 'برتقالي'],
  yellow: ['Yellow', 'Jaune', 'أصفر'],
  green: ['Green', 'Vert', 'أخضر'],
  olive: ['Olive', 'Olive', 'زيتي'],
  teal: ['Teal', 'Bleu canard', 'أزرق مخضر'],
  navy: ['Navy', 'Bleu marine', 'كحلي'],
  blue: ['Blue', 'Bleu', 'أزرق'],
  purple: ['Purple', 'Violet', 'بنفسجي'],
  gold: ['Gold', 'Doré', 'ذهبي'],
  silver: ['Silver', 'Argenté', 'فضي'],
  multicolour: ['Multicolour', 'Multicolore', 'متعدد الألوان'],
}

// swatch colours (mappings/colour_palette.csv)
export const COLOUR_HEX: Record<string, string> = {
  black: '#000000', white: '#FFFFFF', cream: '#F3EBD8', grey: '#808080', beige: '#D8C3A5',
  brown: '#6F4E37', khaki: '#C3B091', red: '#C0392B', burgundy: '#800020', pink: '#F4A6C1',
  orange: '#F28C28', yellow: '#F4D03F', green: '#2E8B57', olive: '#708238', teal: '#008080',
  navy: '#1F2A44', blue: '#2F6FD6', purple: '#7D3C98', gold: '#D4AF37', silver: '#C0C0C0',
  multicolour: 'conic-gradient(#C0392B, #F4D03F, #2E8B57, #2F6FD6, #7D3C98, #C0392B)',
}

export const PATTERN_LABELS: Labels = {
  solid: ['Solid', 'Uni', 'سادة'],
  striped: ['Striped', 'Rayé', 'مخطط'],
  checked: ['Checked', 'À carreaux', 'مربعات'],
  floral: ['Floral', 'Fleuri', 'مورد'],
  printed: ['Printed', 'Imprimé', 'مطبوع'],
}

export const SEASON_LABELS: Labels = {
  summer: ['Summer', 'Été', 'صيف'],
  winter: ['Winter', 'Hiver', 'شتاء'],
  'mid-season': ['Mid-season', 'Mi-saison', 'ربيع وخريف'],
}

export const OCCASION_LABELS: Labels = {
  casual: ['Casual', 'Décontracté', 'يومي'],
  formal: ['Formal', 'Habillé', 'رسمي'],
  sport: ['Sport', 'Sport', 'رياضة'],
  wedding: ['Wedding', 'Mariage', 'عرس'],
  eid: ['Eid', 'Aïd', 'عيد'],
  work: ['Work', 'Travail', 'عمل'],
}

export const COVERAGE_LABELS: Labels = {
  '1': ['Very open', 'Très découvert', 'مكشوف جدا'],
  '2': ['Open', 'Découvert', 'مكشوف'],
  '3': ['Balanced', 'Équilibré', 'متوسط'],
  '4': ['Covered', 'Couvrant', 'محتشم'],
  '5': ['Fully covered', 'Très couvrant', 'محتشم جدا'],
}

const INDEX: Record<Language, 0 | 1 | 2> = { en: 0, fr: 1, ar: 2 }

/** Label of a schema value in a language (falls back to the raw value). */
export function vocab(table: Labels, value: string, lang: Language): string {
  return table[value]?.[INDEX[lang]] ?? value
}

/** The second print line of a ticket: Arabic under Latin text, English under Arabic. */
export function secondLine(table: Labels, value: string, lang: Language): string {
  return table[value]?.[lang === 'ar' ? 0 : 2] ?? ''
}
