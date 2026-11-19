/* 優惠夾：「今天吃什麼」與「下一樣買什麼」推薦（純前端規則，不呼叫 Gemini）
 * 用法（index.html 讀完 data/coupons.json、prepare() 之後）：
 *   const r = Recommend.run(deals, {fav: st.fav, used: st.used, me: st.me});
 *   r.meal  → {key:'lunch', label:'午餐'}
 *   r.eat   → 最多 3 筆 {d, why}（d 是 deals 裡的優惠，why 是推薦原因，例如「3 天後到期」）
 *   r.buy   → 最多 3 筆 {d, why}
 * deals 每筆需要 index.html prepare() 加上的欄位：days、cat、sub、cname。
 * 優惠的 meal／price／item 欄位由每日更新時 Gemini 順便標記；舊資料沒有時，用子分類和標題猜。
 */
(function () {
  const MEAL = {breakfast: '早餐', lunch: '午餐', snack: '下午茶', dinner: '晚餐', late: '宵夜'};

  // 依現在時間決定時段（瀏覽器的本地時間，台灣使用者就是台灣時間）
  function mealNow(date) {
    const h = date.getHours();
    if (h >= 5 && h < 10) return 'breakfast';
    if (h >= 10 && h < 14) return 'lunch';
    if (h >= 14 && h < 17) return 'snack';
    if (h >= 17 && h < 21) return 'dinner';
    return 'late';
  }

  // 沒有 meal 標記時，依子分類猜適合的時段
  const SUB_MEALS = {
    drink: ['breakfast', 'snack', 'drink'],
    fast: ['breakfast', 'lunch', 'dinner', 'late'],
    dine: ['lunch', 'dinner'],
    delivery: ['lunch', 'dinner', 'late'],
  };
  function mealsOf(d) {
    const m = Array.isArray(d.meal) && d.meal.length ? d.meal : (SUB_MEALS[d.sub] || []);
    return new Set(m.includes('drink') ? [...m, 'snack'] : m);  // 飲料也算下午茶
  }

  function priceOf(d) {
    if (d.price > 0) return d.price;
    // 從標題找價錢；「現折 10 元」「滿 400 送 400」這類是折扣金額或門檻，不是售價
    const t = String(d.title);
    for (const m of t.matchAll(/(?:\$|NT\$?)\s?(\d{2,5})|(\d{2,5})\s*元/g)) {
      if (/[折減省送滿回饋]/.test(t.slice(Math.max(0, m.index - 3), m.index))) continue;
      return +(m[1] || m[2]);
    }
    return null;
  }

  // 同一天、同一時段排出來的順序固定，隔天換一批
  function seed(s) {
    let h = 2166136261;
    for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
    return (h >>> 0) / 4294967296;
  }
  function ymd(date) {
    return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
  }

  // 每月檔期（依研究報告的促銷月曆）：符合的子分類加分，並顯示原因
  const SEASON = {
    1: {subs: ['mart', 'online'], why: '年貨檔期'},
    2: {subs: ['mart', 'online'], why: '春節檔期'},
    6: {subs: ['online', 'tech', 'daily'], why: '618 檔期'},
    7: {subs: ['stay', 'transit'], why: '暑假出遊'},
    9: {subs: ['online', 'tech'], why: '99 購物節'},
    10: {subs: ['daily', 'online', 'mart'], why: '週年慶檔期'},
    11: {subs: ['online', 'daily', 'tech', 'mart'], why: '雙 11／週年慶檔期'},
    12: {subs: ['online', 'tech', 'stay'], why: '雙 12／年末檔期'},
  };

  // 限定對象的優惠：使用者沒設定身分或身分不符就不推
  function audOk(d, me) {
    return !d.aud || !d.aud.length || d.aud.some(a => me.has(a));
  }
  function expireWhy(d) {
    if (d.days === 0) return '今天到期';
    if (d.days != null && d.days <= 3) return `${d.days} 天後到期`;
    return '';
  }

  // 依分數排序，每家店最多一筆
  function pick(list, n) {
    list.sort((a, b) => b.score - a.score);
    const seen = new Set(), out = [];
    for (const x of list) {
      if (seen.has(x.d.store)) continue;
      seen.add(x.d.store);
      out.push({d: x.d, why: x.why.filter(Boolean).slice(0, 2).join('・')});
      if (out.length >= n) break;
    }
    return out;
  }

  function run(deals, opt = {}) {
    const now = opt.now || new Date();
    const used = opt.used || new Set(), fav = opt.fav || new Set(), me = new Set(opt.me || []);
    const day = ymd(now);
    const meal = opt.meal || mealNow(now);
    const marked = deals.filter(d => fav.has(d.id) || used.has(d.id));
    const favStores = new Set(marked.map(d => d.store));
    const subCount = {};
    marked.forEach(d => { subCount[d.sub] = (subCount[d.sub] || 0) + 1; });
    const live = deals.filter(d => !used.has(d.id) && audOk(d, me) && (d.days == null || d.days >= 0));

    // 1. 今天吃什麼
    const eat = live
      .filter(d => d.cat === 'food' && !['plan', 'trial'].includes(d.type) && mealsOf(d).has(meal))
      .map(d => {
        const why = [];
        let score = seed(d.id + day + meal) * 2;  // 每天換一批
        if (favStores.has(d.store)) { score += 3; why.push('你收藏過這家'); }
        if (d.aud && d.aud.some(a => me.has(a))) { score += 2; why.push('符合你的身分'); }
        const ex = expireWhy(d);
        if (ex) { score += 2; why.push(ex); }
        const p = priceOf(d);
        if (p) { score += p <= 150 ? 1.5 : 0.5; why.push(`$${p} 起`); }
        if (Array.isArray(d.meal) && d.meal.includes(meal)) score += 1;  // 有明確標時段的優先
        return {d, score, why};
      });
    // 這個時段的優惠不到 3 家時，用其他美食優惠補（分數較低，排在後面）
    if (new Set(eat.map(x => x.d.store)).size < 3) {
      const have = new Set(eat.map(x => x.d.id));
      live.filter(d => d.cat === 'food' && !['plan', 'trial'].includes(d.type) && !have.has(d.id))
        .forEach(d => {
          const p = priceOf(d);
          eat.push({d, score: seed(d.id + day) - 5, why: [expireWhy(d), p ? `$${p} 起` : '']});
        });
    }

    // 2. 下一樣買什麼（美食以外）
    const season = SEASON[now.getMonth() + 1];
    const buy = live
      .filter(d => d.cat && d.cat !== 'food')
      .map(d => {
        const why = [];
        let score = seed(d.id + day) * 1.5;
        if (subCount[d.sub]) { score += Math.min(subCount[d.sub], 3); why.push('你常看的類別'); }
        if (favStores.has(d.store)) score += 1;
        const ex = expireWhy(d);
        if (ex) { score += 2; why.push(ex); }
        if (season && season.subs.includes(d.sub)) { score += 1.5; why.push(season.why); }
        if (d.aud && d.aud.some(a => me.has(a))) { score += 1.5; why.push('符合你的身分'); }
        return {d, score, why};
      });

    return {meal: {key: meal, label: MEAL[meal]}, eat: pick(eat, 3), buy: pick(buy, 3)};
  }

  const api = {run, mealNow, mealsOf, priceOf, MEAL};
  if (typeof module !== 'undefined') module.exports = api;
  else window.Recommend = api;
})();
