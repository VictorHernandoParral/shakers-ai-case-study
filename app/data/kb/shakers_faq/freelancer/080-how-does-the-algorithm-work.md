---
title: "How does the algorithm work?"
audience: freelancer
source: shakers_faq
ordinal: 80
relpath: shakers_faq/freelancer/080-how-does-the-algorithm-work.md
tags: [faq]
---

# How does the algorithm work?

**Q:** How does the algorithm work?

**A:** To calculate the match, we use a hybrid approach that combines collaborative filtering and content-based filtering techniques. Collaborative filtering is based on prior information provided by users, both freelancers and clients (variables that we have categorized as "base" variables and "accuracy" variables).

On the other hand, content-based filtering uses specific information about each candidate and job (such as skills and experience) to recommend similar jobs or candidates. These techniques are implemented in an deep learning architecture that improves the accuracy of our recommendation systems and improves our accuracy with each project and each candidate.

Variables used by the algorithm

Base variables

These are required in order to calculate a match percentage. They are used to calculate a base match percentage and ensure that the minimum technical requirements for applying to a project are always met.

Freelancer's knowledge: naturally, we take into account a freelancer's technical knowledge (specialties, super specialties, skills, and tools they know how to use).

Freelancer's experience: we use information about the skills developed in past projects.

Project requirements: the set of knowledge and skills that a client demands for their project.

This way, a user who has the skills "WordPress" or "Web Design" validated in their profile will have a high "base" match percentage with projects that require those skills.

Similarly, a user who has no knowledge of a technology such as "React" will never be able to have a high enough match percentage to apply for a "React" project.

Accuracy variables

The second set of variables allows us to adjust the match percentage based on criteria beyond strictly professional ones, rewarding users who have a higher level of motivation and cultural fit with a project.

At Shakers, we have a mantra: a motivated worker will always deliver better results than one who is only looking for a paycheck at the end of the month. That's why we should always try to find candidates who stand out not only for their skills, but also for their desire to participate in a project.
