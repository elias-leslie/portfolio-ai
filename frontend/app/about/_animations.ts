export const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
}

export const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.08,
    },
  },
}
