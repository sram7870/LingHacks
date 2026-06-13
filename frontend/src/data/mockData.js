const MOCK_DATA = {
  shopping_list: [
    "olive oil",
    "yellow onion",
    "vegetable broth",
    "canned crushed tomatoes",
    "garlic",
    "granulated sugar",
    "black pepper",
    "fresh basil",
    "heavy cream",
  ],
  user_location: { city: "Maryland Heights", region: "Missouri", lat: 38.714, lng: -90.444 },
  nutrition_report: {
    nutrition_scores: {
      calories: 420,
      protein_g: 9,
      carbs_g: 38,
      fat_g: 26,
      fiber_g: 6,
      protein_score: 5,
      vegetable_score: 8,
      carb_score: 6,
      fat_score: 5,
      health_rating: "Good",
    },
  },
  substitutions: {
    "heavy cream": ["Cashew cream", "Half-and-Half", "Coconut milk"],
    "fresh basil": ["Dried basil", "Fresh oregano"],
    "canned crushed tomatoes": ["Fresh diced tomatoes", "Tomato passata"],
  },
  recommended_stores: [
    {
      store_name: "ALDI",
      items: [
        { item: "olive oil", price: 4.49 },
        { item: "yellow onion", price: 0.79 },
        { item: "vegetable broth", price: 1.99 },
        { item: "canned crushed tomatoes", price: 1.49 },
        { item: "garlic", price: 0.99 },
        { item: "granulated sugar", price: 2.29 },
        { item: "black pepper", price: 1.79 },
        { item: "fresh basil", price: 1.99 },
        { item: "heavy cream", price: 2.49 },
      ],
    },
    {
      store_name: "Trader Joe's",
      items: [
        { item: "olive oil", price: 6.99 },
        { item: "yellow onion", price: 1.29 },
        { item: "vegetable broth", price: 2.49 },
        { item: "canned crushed tomatoes", price: 1.99 },
        { item: "garlic", price: 1.49 },
        { item: "granulated sugar", price: 2.99 },
        { item: "black pepper", price: 2.49 },
        { item: "fresh basil", price: 2.49 },
        { item: "heavy cream", price: 3.49 },
      ],
    },
    {
      store_name: "Whole Foods",
      items: [
        { item: "olive oil", price: 9.99 },
        { item: "yellow onion", price: 1.49 },
        { item: "vegetable broth", price: 3.49 },
        { item: "canned crushed tomatoes", price: 2.99 },
        { item: "garlic", price: 1.99 },
        { item: "granulated sugar", price: 3.99 },
        { item: "black pepper", price: 3.49 },
        { item: "fresh basil", price: 2.99 },
        { item: "heavy cream", price: 4.49 },
      ],
    },
  ],
  optimized_route: [
    { stop: 1, store_name: "ALDI", distance_km: 1.4, lat: 38.71, lng: -90.45 },
    { stop: 2, store_name: "Trader Joe's", distance_km: 2.6, lat: 38.72, lng: -90.43 },
  ],
};

export default MOCK_DATA;
